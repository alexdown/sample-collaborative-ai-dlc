# Tasks: KiroCrew-managed AgentCore execution plane

## Status

- Requirements: Complete
- Design: Complete
- Implementation: Not started

## Execution rules

- Keep every task traceable to requirements and design sections.
- Preserve original AgentCore workspace, credential, and Git behavior unless a task explicitly replaces it.
- Add tests before or with behavior.
- Never introduce the Collaborative AI-DLC frontend or full application backend as a dependency.
- Keep the KiroCrew app namespaced and removable.

## 1. Freeze protocol and compatibility contracts

- [ ] 1.1 Define versioned Assignment Envelope and Assignment Result schemas. _(R10)_
- [ ] 1.2 Define canonical JSON serialization and Agent Snapshot hashing. _(R4, R10)_
- [ ] 1.3 Define deterministic intent/lane session IDs and branch names. _(R6, R10)_
- [ ] 1.4 Define typed provisioning, compatibility, credential, workspace, CLI, Git, gate, timeout, and cancellation errors. _(R10, R12)_
- [ ] 1.5 Add golden fixtures and round-trip/idempotency tests.

## 2. Extract the minimal AgentCore runner

- [ ] 2.1 Create a runner package from the original AgentCore HTTP/runtime command surface. _(R2, R3)_
- [ ] 2.2 Remove Neptune, DynamoDB workflow-state, WebSocket UI, and full-platform dependencies. _(R1)_
- [ ] 2.3 Retain session storage, `/ping`, `/invocations`, stop/resume, and structured output.
- [ ] 2.4 Add protocol-version and runtime-capability endpoints. _(R3, R10)_
- [ ] 2.5 Add unit tests proving the runner imports and starts without the removed backend.

## 3. Build the all-CLI runner image

- [ ] 3.1 Pin Kiro CLI, Claude Code, Codex, OpenCode, Git, Bun, and required adapters. _(R3)_
- [ ] 3.2 Verify binary/package digests and emit a software inventory.
- [ ] 3.3 Run non-root with persistent workspace and ephemeral per-CLI state locations. _(R11)_
- [ ] 3.4 Add per-CLI version/capability probes and fail-closed startup checks.
- [ ] 3.5 Add image build and vulnerability/secret scanning gates.

## 4. Implement KiroCrew integration onboarding

- [ ] 4.1 Add namespaced AWS account/Region connection settings. _(R1, R13)_
- [ ] 4.2 Implement `ensure_runtime` discovery and compatibility comparison. _(R2)_
- [ ] 4.3 Render the infrastructure confirmation with account, Region, image digest, resources, cost-bearing components, and teardown path.
- [ ] 4.4 Add idempotent customer-account deployment for ECR, AgentCore runtime, IAM, VPC networking, broker, and logging.
- [ ] 4.5 Verify health/capabilities before enabling **Start Intent**.
- [ ] 4.6 Add diagnose, update, rollback, and teardown actions. _(R12)_
- [ ] 4.7 Test create/no-op/update/failure/rollback plans.

## 5. Implement KiroCrew Connections → broker integration

- [ ] 5.1 Map KiroCrew connection setup/status to one cloud-redeemable binding. _(R5; Q3-D)_
- [ ] 5.2 Preserve original provider adapters for GitHub, GitLab, Bitbucket, and CodeCommit. _(R5; Q4-C)_
- [ ] 5.3 Preserve signed grant claims, expiry, active-execution, project, repository, provider, and access checks.
- [ ] 5.4 Preserve committer identity and binding invalidation behavior.
- [ ] 5.5 Preserve temporary `GIT_ASKPASS` and credential-free remotes.
- [ ] 5.6 Add equivalent opaque grants for Kiro and Bedrock model credentials. _(R11; Q9-A)_
- [ ] 5.7 Add provider matrix, denial, expiry, refresh, redaction, and disconnect tests.

## 6. Implement Agent Snapshot Compiler

- [ ] 6.1 Resolve stage instructions, selected persona, knowledge, layered rules, custom rules, context, attachments, model/tier, and MCP/tool contract from KiroCrew-local state. _(R4; Q5)_
- [ ] 6.2 Exclude secrets, local absolute paths, unrelated memory/lessons, hooks, global resources, and full home directories.
- [ ] 6.3 Produce canonical snapshot and hash; pin it to assignment attempt/revision.
- [ ] 6.4 Add typed compatibility analysis per CLI before dispatch.
- [ ] 6.5 Record exclusions/exceptions in the assignment and UI.
- [ ] 6.6 Add snapshot determinism, bound, redaction, and incompatibility tests.

## 7. Implement automatic intent workspace bootstrap

- [ ] 7.1 Port repository validation and multi-repository target layout. _(R5)_
- [ ] 7.2 Port clone/reuse with hooks disabled and temporary read grants.
- [ ] 7.3 Verify expected base SHA before branch creation.
- [ ] 7.4 Port empty-repository initialization and default-branch behavior.
- [ ] 7.5 Create and publish intent branch automatically.
- [ ] 7.6 Port workspace-presence check and automatic reclone/restore.
- [ ] 7.7 Add clone/auth/base mismatch/empty/multi-repo/restore tests.

## 8. Implement engine-owned Git durability

- [ ] 8.1 Port runtime-file excludes and deterministic commit attribution. _(R8)_
- [ ] 8.2 Port commit retries, ENOSPC recovery, and dirty-work detection.
- [ ] 8.3 Port authenticated push with retry and remote-head verification.
- [ ] 8.4 Port deterministic no-ff lane merge and conflict handling.
- [ ] 8.5 Return exact base/commit/changed-path/check/push evidence.
- [ ] 8.6 Add ancestry/protected-path/exact-SHA verification in KiroCrew before result acceptance.
- [ ] 8.7 Add local remote tests for every durability and conflict path.

## 9. Implement per-CLI materialization and execution

- [ ] 9.1 Port Kiro materialization and headless invocation. _(R3, R4)_
- [ ] 9.2 Port Claude Code rules/MCP/session materialization and invocation.
- [ ] 9.3 Port Codex private home/config/rules/MCP/session materialization and invocation.
- [ ] 9.4 Port OpenCode inline config/rules/MCP/session materialization and invocation.
- [ ] 9.5 Normalize output, usage, credentials errors, questions, permissions, and completion results.
- [ ] 9.6 Add per-CLI fresh/resume/crash/timeout/compatibility tests.

## 10. Implement mixed-CLI routing

- [ ] 10.1 Define versioned routing policy over stage/role, unit kind, capabilities, model availability, policy, and cost. _(R7; Q6-C)_
- [ ] 10.2 Render selected CLI/model/rationale before dispatch.
- [ ] 10.3 Allow authorized human override and audit it.
- [ ] 10.4 Pin route for assignment continuation; prohibit silent fallback.
- [ ] 10.5 Add concurrent Kiro/Claude/Codex/OpenCode lane test using one runtime image.

## 11. Implement session and lane orchestration

- [ ] 11.1 Allocate one deterministic Intent Session per intent. _(R6; Q7-A)_
- [ ] 11.2 Allocate one deterministic Lane Session per concurrent `(intent, section, unit)`.
- [ ] 11.3 Port automatic lane clone/branch initialization.
- [ ] 11.4 Dispatch only dependency-ready units under concurrency/budget limits.
- [ ] 11.5 Serialize deterministic merges and release lane sessions after settlement.
- [ ] 11.6 Restore/reconcile sessions after KiroCrew restart or AgentCore storage expiry.
- [ ] 11.7 Add parallel DAG, retry, skip, cancel, restart, and recovery tests.

## 12. Implement questions, permissions, and gates

- [ ] 12.1 Normalize remote question/permission responses into KiroCrew pending decisions. _(R9)_
- [ ] 12.2 Render decisions in originating dashboard/channel surfaces.
- [ ] 12.3 Authorize answers from permitted originating-session users and record actor/basis/time. _(Q11-B)_
- [ ] 12.4 Resume the same AgentCore/CLI session and snapshot.
- [ ] 12.5 Release parked compute while preserving eligible session storage.
- [ ] 12.6 Recover expired sessions from durable branch and explicit continuation context.
- [ ] 12.7 Add no-silent-approval, duplicate-answer, timeout, restart, and stale-revision tests.

## 13. Integrate KiroCrew local state and UI

- [ ] 13.1 Persist runtime deployment, intent, assignment, session, route, snapshot, result, review, and gate identities locally. _(R1, R10)_
- [ ] 13.2 Add compare-and-set transition and replay/idempotency handling.
- [ ] 13.3 Add intent creation, progress, worker activity, pending decision, retry/requeue, cancel, and completion surfaces using existing KiroCrew UI patterns.
- [ ] 13.4 Add runtime readiness and capability status to integration settings.
- [ ] 13.5 Keep all app resources namespaced and removable.
- [ ] 13.6 Add restart/reconciliation and uninstall-isolation tests.

## 14. Add security and observability gates

- [ ] 14.1 Validate least-privilege IAM and VPC-by-default networking. _(R11; Q10-B)_
- [ ] 14.2 Add image/protocol/CLI/snapshot/runtime identity to every audit record.
- [ ] 14.3 Redact credentials from snapshots, logs, metrics, failures, and results.
- [ ] 14.4 Report session/stage/unit duration, selected CLI/model, tokens/credits, and cost when available. _(R12)_
- [ ] 14.5 Add CloudWatch dashboards/alarms for runtime invocation, failure, latency, and concurrency.
- [ ] 14.6 Add abuse, injection, credential-leak, unauthorized-gate, and cross-intent isolation tests.

## 15. End-to-end qualification

- [ ] 15.1 Run one intent on each supported CLI.
- [ ] 15.2 Run one intent with concurrent units split across at least three CLIs.
- [ ] 15.3 Prove automatic deployment, clone, branch, commit, push, merge, park, resume, and teardown.
- [ ] 15.4 Prove customer setup requires no Remote Crew, CLI installation, host checkout, or manual branch creation.
- [ ] 15.5 Prove KiroCrew restart and AgentCore session-storage expiry recovery.
- [ ] 15.6 Complete security review, threat model, operational runbook, and cost characterization.
- [ ] 15.7 Replace the current manual mixed-crew guidance with the qualified AgentCore execution path.

## Completion criteria

- All requirements R1–R13 have passing acceptance evidence.
- One shared runtime executes concurrent per-intent and per-unit sessions.
- Kiro, Claude Code, Codex, and OpenCode run from one image with normalized results.
- Repositories and branches are prepared automatically.
- KiroCrew agent semantics are projected according to the original materialization contract.
- No coding CLI receives Git credentials or owns merges.
- No customer-facing Collaborative AI-DLC UI or manually maintained Remote Crew is required.
