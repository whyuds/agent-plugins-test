"""Small offline, read-only MCP stdio probe. Python 3.10+, standard library only."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")
PACKAGE_FILES = (
    "release.json", "plugin.json", ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json",
    "mcp.json", ".mcp.json", "mcp.cursor.json", "scripts/server.py",
    "skills/update-probe-check/SKILL.md", "web/app.html", "web/THIRD-PARTY-NOTICES.txt",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for name in PACKAGE_FILES:
        digest.update(name.encode("utf-8") + b"\0")
        digest.update((root / name).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        self.code, self.message = code, message


class Probe:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.release = json.loads((root / "release.json").read_text(encoding="utf-8"))
        # Freeze the UI with the process: disk updates must not impersonate a live upgrade.
        self.ui_html = (root / "web/app.html").read_bytes()
        self.ui_sha256 = hashlib.sha256(self.ui_html).hexdigest()
        self.ui_uri = f"ui://update-probe/{self.release['build_id']}-{self.ui_sha256[:12]}.html"
        self.package_sha256 = fingerprint(root)
        self.instance_id = str(uuid.uuid4())
        self.started_at = utc_now()
        self.protocol = None
        self.ready = False
        self.client_info = {}
        self.call_count = 0

    def tools(self) -> list[dict]:
        nonce = {"type": "string", "minLength": 1, "maxLength": 120,
                 "description": "Fresh test label echoed by the live process; do not send secrets."}
        annotations = {"readOnlyHint": True, "destructiveHint": False,
                       "idempotentHint": True, "openWorldHint": False}
        label = f"{self.release['version']} {self.release['marker']}"
        output = {"type": "object", "properties": {
            "version": {"type": "string"}, "marker": {"type": "string"},
            "nonce": {"type": "string"}, "ui_marker": {"type": "string"},
            "ui_resource_uri": {"type": "string"}, "ui_sha256": {"type": "string"},
            "disk_matches_startup": {"type": "boolean"}},
            "required": ["version", "marker", "nonce", "ui_marker", "ui_resource_uri", "ui_sha256", "disk_matches_startup"],
            "additionalProperties": True}
        items = [
            {"name": "probe_release", "description": f"Read live Update Probe version and package hashes ({label}). Offline; no account access.",
             "inputSchema": {"type": "object", "properties": {"nonce": nonce},
                             "required": ["nonce"], "additionalProperties": False}, "annotations": annotations},
            {"name": "probe_sum", "description": f"Add two bounded integers using the installed Update Probe MCP ({label}).",
             "inputSchema": {"type": "object", "properties": {
                 "nonce": nonce, "a": {"type": "integer", "minimum": -1000000, "maximum": 1000000},
                 "b": {"type": "integer", "minimum": -1000000, "maximum": 1000000}},
                 "required": ["nonce", "a", "b"], "additionalProperties": False}, "annotations": annotations},
        ]
        items.append({"name": "probe_ui", "description": f"Open the interactive Update Probe MCP App ({label}): UI/server version comparison and real MCP sum buttons. No login or network needed.",
                      "inputSchema": items[0]["inputSchema"], "annotations": annotations,
                      "_meta": {"ui": {"resourceUri": self.ui_uri, "visibility": ["model", "app"]},
                                "openai/outputTemplate": self.ui_uri}})
        for item in items:
            if self.protocol == "2025-06-18":
                item["outputSchema"] = output if item["name"] != "probe_sum" else {
                    **output, "properties": {**output["properties"], "a": {"type": "integer"},
                                             "b": {"type": "integer"}, "sum": {"type": "integer"}},
                    "required": [*output["required"], "a", "b", "sum"]}
        return items

    def read_resource(self, params: dict) -> dict:
        # MCP clients may attach standard request metadata (e.g. progress tokens).
        # Only the exact advertised URI can select content; no filesystem paths are accepted.
        if params.get("uri") != self.ui_uri:
            raise RpcError(-32602, "Unknown UI resource; read the exact URI advertised by probe_ui")
        return {"contents": [{"uri": self.ui_uri, "mimeType": "text/html;profile=mcp-app",
                              "text": self.ui_html.decode("utf-8"), "_meta": {
                                  "ui": {"prefersBorder": True, "csp": {"connectDomains": [], "resourceDomains": []}},
                                  "openai/widgetPrefersBorder": True,
                                  "openai/widgetCSP": {"connect_domains": [], "resource_domains": []}}}]}

    def evidence(self, nonce: str) -> dict:
        try:
            disk_hash = fingerprint(self.root)
            disk_release = json.loads((self.root / "release.json").read_text(encoding="utf-8"))
            disk_error = None
        except (OSError, ValueError):
            disk_hash, disk_release, disk_error = None, None, "Installed package unavailable or invalid"
        return {
            "plugin": "update-probe", **self.release,
            "nonce": nonce, "observed_at": utc_now(),
            "instance_id": self.instance_id, "started_at": self.started_at,
            "call_count": self.call_count, "package_sha256": self.package_sha256,
            "disk_package_sha256": disk_hash, "disk_release": disk_release,
            "disk_matches_startup": disk_hash == self.package_sha256, "disk_error": disk_error,
            "loader_route": os.environ.get("UPDATE_PROBE_LOADER", "direct-not-host-installed"),
            "client_info": self.client_info, "protocol_version": self.protocol,
            "installed_root": str(self.root),
            "ui_resource_uri": self.ui_uri, "ui_sha256": self.ui_sha256,
        }

    def call_tool(self, params: dict) -> dict:
        name = params.get("name")
        if name not in ("probe_release", "probe_sum", "probe_ui"):
            raise RpcError(-32602, "Unknown tool")
        args = params.get("arguments", {})
        expected = {"nonce", "a", "b"} if name == "probe_sum" else {"nonce"}
        if not isinstance(args, dict) or set(args) != expected:
            raise RpcError(-32602, "Arguments must match the tool input schema")
        if not isinstance(args["nonce"], str) or not 1 <= len(args["nonce"]) <= 120:
            raise RpcError(-32602, "nonce must be a string of 1 to 120 characters")
        if name == "probe_sum" and any(type(args[k]) is not int or abs(args[k]) > 1000000 for k in ("a", "b")):
            raise RpcError(-32602, "a and b must be integers between -1000000 and 1000000")
        self.call_count += 1
        evidence = self.evidence(args["nonce"])
        if name == "probe_sum":
            evidence.update(a=args["a"], b=args["b"], sum=args["a"] + args["b"])
        result = {"content": [{"type": "text", "text": json.dumps(evidence, ensure_ascii=False)}], "isError": False}
        if self.protocol == "2025-06-18":
            result["structuredContent"] = evidence
        return result

    def handle(self, request) -> dict | None:
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid JSON-RPC request"}}
        method = request["method"]
        if "id" not in request:
            if method == "notifications/initialized" and self.protocol:
                self.ready = True
            return None
        request_id = request["id"]
        try:
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise RpcError(-32602, "params must be an object")
            if method == "ping":
                result = {}
            elif method == "initialize":
                if self.protocol is not None:
                    raise RpcError(-32600, "Already initialized")
                requested = params.get("protocolVersion")
                if not isinstance(requested, str) or not isinstance(params.get("clientInfo"), dict) or not isinstance(params.get("capabilities"), dict):
                    raise RpcError(-32602, "initialize requires protocolVersion, clientInfo, and capabilities")
                self.protocol = requested if requested in PROTOCOLS else PROTOCOLS[-1]
                self.client_info = {k: params["clientInfo"][k] for k in ("name", "version") if isinstance(params["clientInfo"].get(k), str)}
                result = {"protocolVersion": self.protocol, "capabilities": {
                              "tools": {"listChanged": False}, "resources": {"subscribe": False, "listChanged": False}},
                          "serverInfo": {"name": "update-probe", "version": self.release["version"]}}
            elif not self.ready:
                raise RpcError(-32002, "Initialize the MCP session first")
            elif method == "tools/list":
                if params.get("cursor"):
                    raise RpcError(-32602, "This probe has one tool-list page; no cursor is accepted")
                result = {"tools": self.tools()}
            elif method == "tools/call":
                result = self.call_tool(params)
            elif method == "resources/list":
                if params.get("cursor"):
                    raise RpcError(-32602, "This probe has one resource-list page")
                result = {"resources": [{"uri": self.ui_uri, "name": "Update Probe UI",
                                         "mimeType": "text/html;profile=mcp-app"}]}
            elif method == "resources/templates/list":
                result = {"resourceTemplates": []}
            elif method == "resources/read":
                result = self.read_resource(params)
            else:
                raise RpcError(-32601, "Method not found")
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except RpcError as error:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": error.code, "message": error.message}}


def main() -> None:
    # stdout is reserved for newline-delimited JSON-RPC, including on Windows.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    probe = Probe()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except ValueError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            response = probe.handle(request)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
