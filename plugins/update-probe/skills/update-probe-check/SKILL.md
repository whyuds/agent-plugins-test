---
name: update-probe-check
description: Verify the installed Update Probe demo plugin, its skill marker, and its live MCP version after installation or updates. Use for plugin compatibility and update tests, not normal business tasks.
---

# Update Probe check

This skill copy identifies itself as **SKILL-010-BLUE** (version **0.1.0**).

For an installation/update check:

1. Report the marker above from this loaded skill, not from memory or the remote repository.
2. Use the user's test nonce, or choose a fresh short nonce and report it.
3. Discover and call the installed MCP tool `probe_release` with that nonce.
4. Call the installed MCP tool `probe_sum` with `a=7`, `b=5`, and the same nonce.
5. Report the skill marker, live `version`, `build_id`, `marker`, `loader_route`,
   `instance_id`, `started_at`, `package_sha256`, `disk_matches_startup`,
   echoed nonce, and sum. The sum must be 12. Preserve mismatches as observations.

If either tool is unavailable or fails, report exactly that. Do not run the
server from a terminal, install another copy, fetch repository contents, or
substitute mental arithmetic for an MCP call. Those would invalidate this test.
Tool names may have a host-added namespace; choose the Update Probe tools only.
This demo needs no authentication and must not access business data.
