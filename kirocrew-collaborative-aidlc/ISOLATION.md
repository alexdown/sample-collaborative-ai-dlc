# KiroCrew isolation model

The adapter is designed not to modify or blend into a user's ordinary KiroCrew configuration.

## Default: one reversible, namespaced app

Installing `app.json` uses KiroCrew App Kit ownership rather than copying loose files by hand:

- App id: `collaborative-aidlc-kirocrew`.
- Every declared runtime agent is prefixed `collaborative-aidlc-`.
- KiroCrew materializes app agents under namespaced filenames such as `collaborative-aidlc-kirocrew--collaborative-aidlc-developer.json`.
- The skill has a namespaced app link under `skills/collaborative-aidlc-kirocrew/collaborative-aidlc-kirocrew`; KiroCrew may also expose the globally unique managed flat link `skills/collaborative-aidlc-kirocrew` for discovery.
- Disabling the app deregisters its agent files and skill links.
- Uninstalling removes the app package; `--purge-data` also removes app-owned data.
- Runtime files are confined to the selected project's `aidlc/` directory and carry `aidlc/.kirocrew-collaborative-aidlc.json` ownership metadata.

The adapter declares no custom UI, backend service, MCP server, cron, lifecycle hook, global steering file, default-agent patch, provider credential, Remote Crew record, or automatic approval rule.

Cleanup:

```bash
kirocrew app disable collaborative-aidlc-kirocrew
kirocrew app uninstall collaborative-aidlc-kirocrew
# Use --purge-data only when app-owned retained data should also be deleted.
```

Project artifacts under `<project>/aidlc/` are intentionally retained as the intent record. Delete or archive them separately after review.

## Strong isolation for pilots

For a pilot that must not share sessions, memory, apps, skills, credentials, or agent specs with the normal installation, run a second KiroCrew profile with **both** homes redirected:

```bash
export AIDLC_PROFILE="$HOME/.local/share/collaborative-aidlc-kirocrew"
export KIROCREW_HOME="$AIDLC_PROFILE/crew"
export KIRO_HOME="$AIDLC_PROFILE/kiro"
export KIROCREW_PORT=6777

kirocrew setup
kirocrew app install "/absolute/path/to/kirocrew-collaborative-aidlc"
kirocrew app enable collaborative-aidlc-kirocrew
kirocrew gateway
```

`KIROCREW_HOME` isolates KiroCrew configuration, memory, sessions, apps, and schedules. `KIRO_HOME` separately isolates Kiro/ACP agent specs and Kiro session material. `KIROCREW_PORT` lets the pilot run beside the normal gateway. The isolated profile requires its own agent-harness login and settings.

Do not place the profile inside a source repository and do not commit it: it may contain credentials and transcripts.

## Project-local alternative

A team that does not want to install an app can copy the skill and agent JSON files into a target repository's `.kiro/skills/` and `.kiro/agents/`. That makes the assets project-scoped, but it requires explicit project-skill trust and has weaker lifecycle cleanup than App Kit. The shipped adapter therefore uses the namespaced app as the default and the dedicated-home profile as the strongest option.
