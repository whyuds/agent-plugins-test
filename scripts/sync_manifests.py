"""Generate small host adapters from one release record; never install or push."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "update-probe"
MARKET = "agent-plugins-test"
REPOSITORY = "https://github.com/whyuds/agent-plugins-test"


def render() -> dict[Path, str]:
    release = json.loads((PLUGIN / "release.json").read_text(encoding="utf-8"))
    version = release["version"]
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\+[A-Za-z0-9.-]+)?", version):
        raise ValueError("Use a stable SemVer version, optionally with build metadata")
    title = f"Update Probe {version} {release['marker']}"
    description = f"Offline update test: {version} / {release['marker']} / Skill + MCP UI."
    base = {
        "name": "update-probe", "version": version,
        "description": description, "author": {"name": "whyuds"},
        "repository": REPOSITORY,
    }
    portable = {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", **base}
    codex = {
        **base, "skills": "./skills/", "mcpServers": "./.mcp.json",
        "interface": {
            "displayName": title, "shortDescription": description,
            "longDescription": "Offline Skill, MCP tools and interactive MCP App for installation and update testing.",
            "developerName": "whyuds", "category": "Productivity", "capabilities": [],
            "brandColor": "#0D9488",
            "defaultPrompt": ["Use update-probe-check to verify this installed plugin."],
        },
    }
    cursor = {**base, "skills": "./skills/", "mcpServers": "./mcp.cursor.json"}
    # Portable format defaults cwd to the plugin root: no nonstandard root token.
    server = {"type": "stdio", "command": "python", "args": ["-u", "./scripts/server.py"],
              "env": {"UPDATE_PROBE_LOADER": "portable-default-cwd", "PYTHONDONTWRITEBYTECODE": "1"}}
    portable_mcp = {"$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                    "mcpServers": {"update-probe": server}}
    codex_mcp = {"mcpServers": {"update-probe": {
        **server, "cwd": "./", "env": {**server["env"], "UPDATE_PROBE_LOADER": "codex-relative-cwd"}}}}
    cursor_mcp = {"mcpServers": {"update-probe": {
        **server, "args": ["-u", "${CURSOR_PLUGIN_ROOT}/scripts/server.py"],
        "cwd": "${CURSOR_PLUGIN_ROOT}",
        "env": {**server["env"], "UPDATE_PROBE_LOADER": "cursor-native-root"}}}}
    catalog = {
        "name": MARKET, "owner": {"name": "whyuds"},
        "metadata": {"description": "Isolated plugin installation and update experiments"},
        "plugins": [{"name": "update-probe", "source": "./plugins/update-probe",
                     "description": description, "version": version}],
    }
    # Keep Codex's scaffolded marketplace and its policies as the authority.
    codex_market_path = ROOT / ".agents/plugins/marketplace.json"
    codex_market = json.loads(codex_market_path.read_text(encoding="utf-8"))
    if codex_market["name"] != MARKET or [p["name"] for p in codex_market["plugins"]] != ["update-probe"]:
        raise ValueError("Unexpected Codex marketplace identity or plugin inventory")
    documents = {
        PLUGIN / "plugin.json": portable,
        PLUGIN / ".codex-plugin/plugin.json": codex,
        PLUGIN / ".cursor-plugin/plugin.json": cursor,
        PLUGIN / "mcp.json": portable_mcp,
        PLUGIN / ".mcp.json": codex_mcp,
        PLUGIN / "mcp.cursor.json": cursor_mcp,
        ROOT / ".github/plugin/marketplace.json": catalog,
        ROOT / ".cursor-plugin/marketplace.json": catalog,
    }
    rendered = {path: json.dumps(value, ensure_ascii=False, indent=2) + "\n"
                for path, value in documents.items()}
    template = (ROOT / "templates/SKILL.md").read_text(encoding="utf-8")
    rendered[PLUGIN / "skills/update-probe-check/SKILL.md"] = template.format(**release)
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on drift without editing")
    args = parser.parse_args()
    different = []
    for path, content in render().items():
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        different.append(str(path.relative_to(ROOT)))
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if args.check and different:
        raise SystemExit("Generated files differ: " + ", ".join(different))
    print("Generated files are in sync" if args.check else f"Updated {len(different)} generated files")


if __name__ == "__main__":
    main()
