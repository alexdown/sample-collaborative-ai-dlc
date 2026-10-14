# Use Collaborative AI-DLC through KiroCrew

The repository includes an adapter for teams already using KiroCrew. It projects a pinned 25-stage AI-DLC profile, specialist roles, clean-room review steps, file-native state, unit-of-work lanes, and explicit human gates into the existing KiroCrew experience. Customers can use a tool that is released and supported instead of adopting another custom UI.

## What it replaces

For this integration path, KiroCrew provides the customer-facing dashboard, authentication, conversations, agent harness, approvals, and remote-host access. The original Collaborative AI-DLC frontend and AWS control plane remain the reference implementation and are not deployed.

## Install

```bash
cd kirocrew-collaborative-aidlc
python3 scripts/validate_bundle.py
kirocrew app install "$(pwd)"
kirocrew app enable collaborative-aidlc-kirocrew
kirocrew doctor
```

Bind a KiroCrew chat to the repository you want to change, select the `collaborative-aidlc-conductor` agent, and choose **Start Collaborative AI-DLC intent** from the command bar.

## Coding agents

Stable KiroCrew 0.8 runs each gateway on one selected ACP harness, including Kiro, Claude Code, Codex, or OpenCode. Choose and verify it under **Settings → Developer → Agent Backend** before starting an intent.

For mixed-harness delivery, connect separately configured gateways as Remote Crews under one hub dashboard. The conductor assigns only dependency-ready unit branches, remote specialists return commits and evidence, and the conductor merges, reviews, and records gates centrally. Follow the repository's [mixed coding-agent crews guide](https://github.com/aws-samples/sample-collaborative-ai-dlc/blob/main/kirocrew-collaborative-aidlc/skills/collaborative-aidlc-kirocrew/references/mixed-crews.md) for exact Kiro, Claude Code, Codex, and OpenCode setup plus SSH/SSM registration and handoff procedures.

## Remote hosts

Install the adapter and agent CLIs on each Remote Crew machine. **New chat on crew** is a feature preview in KiroCrew 0.8: the hub owns the conversation row, transcript, history, and search record, while prompts, tools, models, and workspace access execute remotely. Cross-host lane fan-out is a supervised source-control handoff, not a remote target on `spawn_run`.

## Differences from the full platform

The adapter uses markdown and JSON instead of Neptune and DynamoDB. It does not reproduce live Yjs co-editing, graphical traceability, engine-owned git merges, or exact per-stage cost accounting. See the repository's [KiroCrew integration plan](https://github.com/aws-samples/sample-collaborative-ai-dlc/blob/main/kirocrew-collaborative-aidlc/PLAN.md) for the replacement map, isolation model, and follow-up work.
