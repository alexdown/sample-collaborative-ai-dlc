---
name: collaborative-aidlc-kirocrew
description: Run the pinned AI-DLC intent through KiroCrew with specialist agents, deterministic state, reviews, sensors, and human gates.
always: false
triggers: aidlc intent, start intent, run aidlc, continue aidlc, intent status
inject_on_trigger: true
---

# Collaborative AI-DLC on KiroCrew

Use KiroCrew as the only participant UI and agent control plane. Do not deploy or call the Collaborative AI-DLC frontend, Neptune, DynamoDB, AgentCore, Cognito, or its Lambda orchestrator.

## Invariants

1. The pinned 25-stage profile is derived from `awslabs/aidlc-workflows@83ed7a812c4024904f2c5e4d744e28077e0a5acd`: 25 stages, 22 human gates, 10 reviewer stages, and five per-unit construction stages.
2. The profile begins from a concrete intent rather than running Ideation. The user must supply that intent; never silently invent one.
3. The Python state machine is the authority for stage order, unit dependencies, status, findings, receipts, and resume. Agents never edit `workflow-state.json`, `aidlc-state.md`, selectors, or audit files directly.
4. Execute only work returned by `status --json`. Never start a later stage because it appears easy or related.
5. Every non-initialization stage ends at an explicit human gate. Never infer approval from silence or from a successful worker result.
6. A reviewer is a clean-room worker. Give it the produced artifacts and declared inputs, not the lead worker transcript.
7. KiroCrew owns agent execution. Use `spawn_run`/`spawn_sub_agents`; do not invoke `claude`, `codex`, `kiro-cli`, or `opencode` directly.
8. The released KiroCrew 0.8 backend selection is gateway-wide. Run every worker on the harness selected under Settings → Developer → Agent Backend; do not claim per-worker backend routing.
9. Verify returned claims by reading artifacts and recorded test output before opening a gate.
10. Never perform deployment or infrastructure mutation without a separate, explicit human confirmation at that stage.

## Locate the runner

The runner is `scripts/workflow.py` relative to this `SKILL.md`. Set `RUNNER` to its absolute path and always pass the target repository as `--project <absolute-project-root>`. The intent chat must use the `collaborative-aidlc-conductor` agent so the required KiroCrew dispatch tools are present.

## Start

When no intent is active:

1. Confirm the chat is bound to the intended repository.
2. Determine `greenfield` or `brownfield` from the user intent and repository contents; report the choice.
3. Initialize:

```bash
python3 "$RUNNER" --project "$PROJECT" init \
  --title "<short title>" \
  --project-type <greenfield|brownfield> \
  --intent "<verbatim user intent>"
```

4. Show the returned intent directory and the first `status --json` result.
5. Ask the human to approve beginning the first domain stage. Initialization itself is deterministic and already recorded.

## Resume and dispatch

Read current work:

```bash
python3 "$RUNNER" --project "$PROJECT" status --json
```

For each returned `{stage, unit}` item:

1. Generate the bounded worker brief:

```bash
python3 "$RUNNER" --project "$PROJECT" context --stage "$STAGE" [--unit "$UNIT"]
```

2. Mark it running only immediately before dispatch:

```bash
python3 "$RUNNER" --project "$PROJECT" start --stage "$STAGE" [--unit "$UNIT"]
```

3. Dispatch `runtimeLead` as the named KiroCrew agent, using the context JSON as the task. Ask each `runtimeSupport` agent for an independent contribution in parallel when listed, then ask the lead to integrate them. Parallel writers must own different files.
4. For `code-generation`, require implementation plus relevant tests in the repository; the markdown outputs summarize that work.
5. Run the repository's relevant tests and the declared deterministic checks. Record concrete commands/results as evidence.
6. Finish the stage:

```bash
python3 "$RUNNER" --project "$PROJECT" finish --stage "$STAGE" [--unit "$UNIT"] --evidence "<checks>"
```

Missing artifacts or fewer than two `##` sections become blocking findings.

## Unit plan

Before approving `units-generation`, register its generated DAG:

```bash
python3 "$RUNNER" --project "$PROJECT" set-units \
  --artifact "<intent-root>/inception/units-generation/unit-of-work-dependency.md" \
  [--walking-skeleton <unit>]
```

The artifact must contain one fenced YAML block:

```yaml
units:
  - name: foundation
    depends_on: []
  - name: feature
    depends_on: [foundation]
```

The runner executes the walking skeleton first. Afterwards it exposes only dependency-ready unit lanes. Independent ready lanes may use one `spawn_run(tasks=[...])` wave.

## Reviewer

If `runtimeReviewer` is present, dispatch that named agent after the lead completes. Provide only: intent, stage contract, consumed artifact paths, produced artifact paths, unit, and sensor/test evidence. Ask for `READY`, `NOT-READY`, or `INCONCLUSIVE`, then record it:

```bash
python3 "$RUNNER" --project "$PROJECT" review --stage "$STAGE" [--unit "$UNIT"] \
  --verdict <READY|NOT-READY|INCONCLUSIVE> --findings "<bounded findings>"
```

A non-READY reviewer verdict is decision support at the gate. Do not rewrite artifacts in the reviewer session.

## Human gate

Present: stage/unit, produced artifact links, support contributions, test/sensor evidence, reviewer verdict, and blocking/advisory findings. Offer exactly:

- **Approve** — only when there are no blocking findings.
- **Request changes** — requires actionable feedback; the same stage becomes revising.
- **Override and approve** — only for displayed overridable findings; requires a reason recorded on the receipt.

Record only the user's explicit choice:

```bash
python3 "$RUNNER" --project "$PROJECT" gate --stage "$STAGE" [--unit "$UNIT"] \
  --decision <approve|request-changes|override-and-approve> [--reason "<reason>"]
```

After a decision, read `status --json` again. Continue only if the user asked for continued/autonomous execution; otherwise report the next stage and stop at the gate.

## Completion

When `status` returns no current work:

1. Run `validate`.
2. Summarize the intent, approved artifacts, code/test changes, override receipts, and outstanding advisory findings.
3. Do not push, deploy, merge, or open a pull request unless the user separately requests it.

## Remote crews and mixed backends

`spawn_run` uses the agent harness selected on that KiroCrew gateway (`kiro`, `claude`, `codex`, `opencode`, etc.). Stable KiroCrew 0.8 does not select a different backend per spawned worker.

When the user requests mixed harnesses, read `references/mixed-crews.md` and follow it exactly. Keep this conductor authoritative for state and gates; use **New chat on crew** for each remote assignment; give each crew a separate dependency-ready branch; require a commit SHA and test evidence; and merge results in DAG order before calling `finish`. Never claim `spawn_run` itself targeted the remote host.
