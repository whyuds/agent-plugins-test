---
name: update-probe-check
description: Verify the installed Update Probe demo plugin, its skill marker, and its live MCP version after installation or updates. Use for plugin compatibility and update tests, not normal business tasks.
---

# Update Probe check

This skill copy identifies itself as **SKILL-021-AMBER** (version **0.2.1**).

For an installation/update check:

1. Report the marker above from this loaded skill, not from memory or the remote repository.
2. Use the user's test nonce, or choose a fresh short nonce and report it.
3. Discover and call the installed MCP tool `probe_release` with that nonce.
4. Call the installed MCP tool `probe_sum` with `a=7`, `b=5`, and the same nonce.
5. Report the skill marker, live `version`, `build_id`, `marker`, `loader_route`,
   `instance_id`, `started_at`, `package_sha256`, `disk_matches_startup`,
   echoed nonce, and sum. The sum must be 12. Preserve mismatches as observations.
6. Call `probe_ui` with the same nonce to open the native MCP App. Ask the user
   to click **刷新服务版本** and **通过 MCP 计算**, then compare the card's own
   UI marker (**UI-021-AMBER**) with the returned service marker. The agent cannot
   infer that the host rendered the card or buttons worked merely from a successful tool result.

If the host does not render MCP Apps, record UI as `unsupported` (if documented)
or `unable` (if unknown), separately from working Skill/MCP tools. A browser
preview or a code-generated imitation is not a passing native client UI test.

If either tool is unavailable or fails, report exactly that. Do not run the
server from a terminal, install another copy, fetch repository contents, or
substitute mental arithmetic for an MCP call. Those would invalidate this test.
Tool names may have a host-added namespace; choose the Update Probe tools only.
This demo needs no authentication and must not access business data.
