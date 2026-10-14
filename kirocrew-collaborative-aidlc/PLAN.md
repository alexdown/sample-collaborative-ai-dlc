# KiroCrew integration plan

## Objective

Use KiroCrew as the customer-facing experience for Collaborative AI-DLC so customers do not need to adopt another custom tool. Project the methodology's stage graph and human governance without deploying the custom Collaborative AI-DLC UI.

## Confirmed source behavior

Collaborative AI-DLC explicitly runs multiple coding agents: Kiro, Claude Code, OpenCode, and Codex. It selects a CLI for each intent and launches a headless session per stage. The pinned 25-stage profile executes initialization, inception, construction, and operation; requires 22 human gates; and assigns clean-room reviewers to 10 stages.

## Replacement map

| Collaborative AI-DLC component     | KiroCrew integration                                                   |
| ---------------------------------- | ---------------------------------------------------------------------- |
| React intent workbench             | Existing KiroCrew dashboard chat, Subagents and Changes panels         |
| Intent compose form                | Command-bar action plus conductor conversation                         |
| AgentCore CLI session              | `spawn_run` with the gateway's selected harness                        |
| Per-intent CLI selector            | KiroCrew Settings → Developer → Agent Backend                          |
| Lambda durable orchestrator        | Conductor skill plus file-native Python state machine                  |
| DynamoDB process rows              | `workflow-state.json` and append-only `audit/events.jsonl`             |
| Neptune artifacts/traceability     | Canonical markdown artifacts, stable slugs and wikilinks               |
| Platform question/validation gates | Explicit KiroCrew chat questions and persisted receipts                |
| Reviewer AgentCore session         | Separate read-only KiroCrew reviewer agent                             |
| Deterministic sensors              | Local artifact validation plus repository test/lint/typecheck commands |
| Parallel construction lanes        | KiroCrew subagent batches constrained by the unit DAG                  |
| Cloud workspace isolation          | KiroCrew local/remote host sandbox and project directory               |
| Cognito/SSO and app roles          | Existing KiroCrew authentication and deployment policy                 |
| Yjs collaborative editing          | Source control plus KiroCrew session collaboration                     |
| Cost dashboard                     | KiroCrew per-agent usage where available; no exact stage-cost parity   |

## Delivered changes

1. Add an App Kit manifest with a command-bar entry and no custom UI.
2. Add a conductor skill defining start/resume, dispatch, review, gate, unit-lane, and completion behavior.
3. Add the conductor and 13 specialist agent configurations under the `collaborative-aidlc-` runtime namespace and app-owned lifecycle.
4. Add no global steering files, hooks, crons, MCP servers, default-agent patches, or backend configuration; document a dedicated `KIROCREW_HOME` + `KIRO_HOME` profile for strict pilot isolation.
5. Add a deterministic state runner implementing the pinned 25-stage profile, native directory selectors, State v7 rendering, unit DAG scheduling, artifact checks, reviewer records, and approval/override receipts.
6. Add bundle validation and a state-machine self-test.
7. Add install, execution, backend-selection, Remote Crew, mixed-harness handoff, and isolation documentation.
8. Link the KiroCrew integration path from the repository README and documentation navigation.

## Deliberately not changed

- Existing platform code, Terraform, frontend, APIs, and tests remain intact.
- No AWS infrastructure is deployed or modified.
- No KiroCrew user configuration, Remote Crew registration, provider credential, or approval bypass is silently changed.
- No automatic git push, deployment, merge, or pull-request creation is introduced.

## Follow-up work for production parity

1. Import full upstream stage and persona bodies at a verified methodology release instead of the bounded role summaries in this first adapter.
2. Add a local typed-item index for requirement → story → component → unit → code traceability.
3. Port required-sections, upstream-coverage, and graph-coverage into standalone sensor commands and store structured verdicts per artifact.
4. Add a supported KiroCrew workflow-library import API; current dynamic workflows cannot host human approval calls, so the conversational conductor remains authoritative.
5. Add optional source-control worktrees and deterministic lane merges.
6. Add stage usage and cost aggregation from KiroCrew subagent receipts.
7. Run a pilot with Kiro, Claude Code, and Codex backends and record harness-specific capability gaps.
