from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/update-probe"
spec = importlib.util.spec_from_file_location("probe_server", PLUGIN / "scripts/server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def request(method, params=None, number=1):
    return {"jsonrpc": "2.0", "id": number, "method": method, "params": params or {}}


def initialize(probe, protocol="2025-06-18"):
    result = probe.handle(request("initialize", {
        "protocolVersion": protocol, "capabilities": {},
        "clientInfo": {"name": "probe-tests", "version": "1"}}))
    probe.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return result


def evidence(reply):
    return json.loads(reply["result"]["content"][0]["text"])


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.probe = server.Probe()
        initialize(self.probe)

    def test_handshake_and_tools(self):
        p = server.Probe()
        reply = initialize(p)
        self.assertEqual(reply["result"]["serverInfo"]["version"], p.release["version"])
        tools = p.handle(request("tools/list"))["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["probe_release", "probe_sum"])
        for tool in tools:
            self.assertTrue(tool["annotations"]["readOnlyHint"])
            self.assertFalse(tool["annotations"]["openWorldHint"])

    def test_fresh_nonce_and_sum(self):
        value = evidence(self.probe.handle(request("tools/call", {
            "name": "probe_sum", "arguments": {"a": 7, "b": 5, "nonce": "中文-round-1"}})))
        self.assertEqual(value["sum"], 12)
        self.assertEqual(value["nonce"], "中文-round-1")
        self.assertTrue(value["disk_matches_startup"])
        self.assertEqual(value["call_count"], 1)
        self.assertEqual(value["client_info"], {"name": "probe-tests", "version": "1"})

    def test_instance_id_is_process_instance_not_release(self):
        self.assertNotEqual(self.probe.instance_id, server.Probe().instance_id)
        self.assertEqual(self.probe.package_sha256, server.Probe().package_sha256)

    def test_invalid_arguments_never_execute(self):
        invalid = [
            {"a": True, "b": 5, "nonce": "bad"}, {"a": 1.5, "b": 5, "nonce": "bad"},
            {"a": 1000001, "b": 5, "nonce": "bad"}, {"a": 1, "b": 2, "nonce": ""},
            {"a": 1, "b": 2, "nonce": "x" * 121}, {"a": 1, "b": 2}, [],
            {"a": 1, "b": 2, "nonce": "bad", "path": "arbitrary-file"},
        ]
        for args in invalid:
            with self.subTest(args=args):
                response = self.probe.handle(request("tools/call", {"name": "probe_sum", "arguments": args}))
                self.assertEqual(response["error"]["code"], -32602)
        self.assertEqual(self.probe.call_count, 0)

    def test_unknown_tool_and_method(self):
        self.assertEqual(self.probe.handle(request("tools/call", {"name": "shell"}))["error"]["code"], -32602)
        self.assertEqual(self.probe.handle(request("execute"))["error"]["code"], -32601)
        self.assertEqual(self.probe.handle(request("ping"))["result"], {})

    def test_notifications_have_no_response(self):
        self.assertIsNone(self.probe.handle({"jsonrpc": "2.0", "method": "notifications/cancelled"}))

    def test_session_state(self):
        p = server.Probe()
        self.assertEqual(p.handle(request("tools/list"))["error"]["code"], -32002)
        self.assertIn("result", initialize(p))
        self.assertEqual(initialize(p)["error"]["code"], -32600)

    def test_protocol_negotiation_and_legacy_output(self):
        for protocol in server.PROTOCOLS:
            p = server.Probe()
            self.assertEqual(initialize(p, protocol)["result"]["protocolVersion"], protocol)
            response = p.handle(request("tools/call", {"name": "probe_release", "arguments": {"nonce": "legacy"}}))
            self.assertEqual("structuredContent" in response["result"], protocol == "2025-06-18")
        self.assertEqual(initialize(server.Probe(), "2099-01-01")["result"]["protocolVersion"], "2025-06-18")

    def test_invalid_envelopes_and_initialize(self):
        for payload in (None, [], "hello", {"jsonrpc": "2.0", "method": 12}):
            self.assertEqual(self.probe.handle(payload)["error"]["code"], -32600)
        self.assertEqual(server.Probe().handle(request("initialize"))["error"]["code"], -32602)

    def test_changed_disk_does_not_fake_live_upgrade(self):
        temp_root = ROOT / "tmp"
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temp:
            copy = Path(temp) / "installed plugin with spaces"
            shutil.copytree(PLUGIN, copy, ignore=shutil.ignore_patterns("__pycache__"))
            p = server.Probe(copy)
            original = p.release["version"]
            changed = {**p.release, "version": "99.0.0", "marker": "TEST-ONLY"}
            (copy / "release.json").write_text(json.dumps(changed), encoding="utf-8")
            observed = p.evidence("changed-disk")
            self.assertEqual(observed["version"], original)
            self.assertEqual(observed["disk_release"]["version"], "99.0.0")
            self.assertFalse(observed["disk_matches_startup"])
            self.assertEqual(server.Probe(copy).release["version"], "99.0.0")

    def test_removed_disk_reported_without_crash(self):
        p = server.Probe()
        p.root = PLUGIN / "not-an-installed-directory"
        value = p.evidence("missing-disk")
        self.assertFalse(value["disk_matches_startup"])
        self.assertIsNotNone(value["disk_error"])

    def test_generated_files_and_manifests(self):
        subprocess.run([sys.executable, str(ROOT / "scripts/sync_manifests.py"), "--check"], check=True, capture_output=True)
        for path in ("plugin.json", ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json"):
            manifest = json.loads((PLUGIN / path).read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], self.probe.release["version"])
            self.assertEqual(manifest["name"], "update-probe")
        for path in (".agents/plugins/marketplace.json", ".github/plugin/marketplace.json", ".cursor-plugin/marketplace.json"):
            market = json.loads((ROOT / path).read_text(encoding="utf-8"))
            self.assertEqual(market["name"], "agent-plugins-test")
            source = market["plugins"][0]["source"]
            relative = source["path"] if isinstance(source, dict) else source
            self.assertEqual((ROOT / relative).resolve(), PLUGIN.resolve())

    def test_real_stdio_for_each_adapter(self):
        messages = [request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "subprocess-test", "version": "1"}}),
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    request("tools/list", number=2),
                    request("tools/call", {"name": "probe_release", "arguments": {"nonce": "stdio"}}, 3),
                    request("tools/call", {"name": "probe_sum", "arguments": {"a": 7, "b": 5, "nonce": "stdio"}}, 4)]
        for config_path in ("mcp.json", ".mcp.json", "mcp.cursor.json"):
            with self.subTest(config=config_path):
                config = json.loads((PLUGIN / config_path).read_text(encoding="utf-8"))["mcpServers"]["update-probe"]
                args = [a.replace("${CURSOR_PLUGIN_ROOT}", str(PLUGIN)) for a in config["args"]]
                cwd = config.get("cwd", str(PLUGIN)).replace("${CURSOR_PLUGIN_ROOT}", str(PLUGIN))
                if not Path(cwd).is_absolute():
                    cwd = str(PLUGIN / cwd)
                completed = subprocess.run([sys.executable, *args], cwd=cwd,
                    env={**os.environ, **config["env"]}, input="\n".join(json.dumps(m) for m in messages) + "\n",
                    capture_output=True, text=True, encoding="utf-8", timeout=10)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stderr, "")
                replies = [json.loads(line) for line in completed.stdout.splitlines()]
                self.assertEqual([r["id"] for r in replies], [1, 2, 3, 4])
                self.assertEqual(evidence(replies[-1])["sum"], 12)
                self.assertEqual(evidence(replies[-1])["loader_route"], config["env"]["UPDATE_PROBE_LOADER"])
                self.assertEqual(evidence(replies[-1])["instance_id"], evidence(replies[-2])["instance_id"])


if __name__ == "__main__":
    unittest.main()
