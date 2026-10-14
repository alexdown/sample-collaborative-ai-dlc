# Collaborative AI-DLC for KiroCrew

This adapter lets customers use Collaborative AI-DLC through KiroCrew instead of adopting another custom UI. KiroCrew supplies the supported customer experience, conversations, agent harness, approvals, subagents, memory, and remote-host access. The adapter supplies bounded AI-DLC role prompts, a conductor protocol, deterministic stage state, basic artifact checks, clean-room review steps, and gate receipts.

It intentionally does **not** deploy the sample's React UI or AWS control plane (CloudFront, Cognito, API Gateway, Lambda, DynamoDB, Neptune, ECS/Yjs, or Bedrock AgentCore).

## Install

Prerequisites: KiroCrew 0.8.0+, Python 3.10+, and a working ACP backend.

```bash
cd kirocrew-collaborative-aidlc
python3 scripts/validate_bundle.py
kirocrew app install "$(pwd)"
kirocrew app enable collaborative-aidlc-kirocrew
kirocrew doctor
```

Restart KiroCrew if you installed a new agent harness after the gateway started.

## Isolation

The default install is one reversible, namespaced App Kit package. Its 14 runtime agents use the `collaborative-aidlc-` prefix, and KiroCrew removes app-owned agent files and skill links when the app is disabled. The adapter creates no global steering files, hooks, crons, MCP servers, provider settings, or default-agent edits. Intent state stays under the selected repository's `aidlc/` directory.

For a pilot with zero shared KiroCrew state, run it with dedicated `KIROCREW_HOME`, `KIRO_HOME`, and `KIROCREW_PORT` values. See [ISOLATION.md](ISOLATION.md) for the exact layout and cleanup commands.

## Run

1. Open the target repository as the project for a KiroCrew dashboard chat.
2. Select the `collaborative-aidlc-conductor` agent.
3. Open the command bar and select **Start Collaborative AI-DLC intent**, or ask: `Start a Collaborative AI-DLC intent for <request>`.
4. Review every stage gate in the chat. State and artifacts are written under the target repository's `aidlc/` directory.

The pinned 25-stage profile begins from a concrete intent, so include users, desired outcome, constraints, and out-of-scope items.

## Coding-agent harness

Stable KiroCrew 0.8 selects one ACP harness for the gateway under **Settings → Developer → Agent Backend**. The intent and its spawned specialists use that harness. Choose Kiro, Claude Code, Codex, or OpenCode before starting, and run `kirocrew doctor` to verify the host.

Per-worker backend routing exists on KiroCrew's later development line but is not assumed by this adapter. Stable KiroCrew 0.8 can supervise manual mixed-harness handoffs through the **Chat on a crew** preview: configure one gateway for each harness, connect them to one hub dashboard, and assign only dependency-ready unit branches. This is not automatic cross-host `spawn_run` routing. See the [mixed coding-agent crews guide](skills/collaborative-aidlc-kirocrew/references/mixed-crews.md) for host setup, capability smoke checks, SSH/SSM registration, branch ownership, handoffs, reviews, merges, and recovery.

## Remote execution

Install this adapter and the desired coding CLI on each Remote Crew host. Create the intent using **New chat on crew** so state and execution live on that host. KiroCrew currently does not expose a Remote Crew target on `spawn_run`; mixed-host lane dispatch therefore requires separate remote sessions and source-control coordination.

## Compatibility and trade-offs

Projected in this first adapter: the pinned 25-stage profile, 22 explicit gates, 10 clean-room review steps, five per-unit stages, walking-skeleton-first scheduling, dependency-ready lanes, native-style AI-DLC directory selectors, State v7 markers, basic required-artifact/heading checks, and an append-only gate/audit record.

Changed: Neptune traceability becomes markdown plus JSON state; KiroCrew replaces the custom workbench; KiroCrew subagents replace AgentCore sessions; source control remains human/KiroCrew managed rather than engine-owned; real-time co-editing, graphical traceability, and stage-level token-cost accounting are not reproduced.

See [PLAN.md](PLAN.md) for the migration plan and boundary decisions.
