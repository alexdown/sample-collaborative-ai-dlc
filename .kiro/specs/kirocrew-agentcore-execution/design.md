# Design: KiroCrew-managed AgentCore execution plane

## Status

- Requirements: Complete
- Design: Complete
- Implementation: Not started

## Design summary

KiroCrew remains the local customer experience and lifecycle authority. A minimal AWS execution plane supplies one shared, digest-pinned AgentCore runtime containing every supported coding CLI. KiroCrew dispatches immutable assignment snapshots to isolated per-intent and per-unit sessions. Runtime code automatically checks out repositories, materializes the selected CLI, executes work, and owns commit/push/merge. Questions and gates return to KiroCrew.

This retains the useful execution machinery from Collaborative AI-DLC without retaining its separate frontend or full application backend.

```text
KiroCrew local control plane
├── Collaborative AI-DLC app
├── local intent/state/gates/audit
├── agent + stage snapshot compiler
├── deterministic CLI router
├── KiroCrew Connections
└── AgentCore dispatcher
        │ signed assignment + credential grant
        ▼
Customer AWS account
├── ECR: one all-CLI runner image
├── AgentCore: one shared runtime resource
│   ├── Intent Session A
│   ├── Intent Session B
│   ├── Intent A / Lane X
│   └── Intent A / Lane Y
├── minimal credential broker
├── encrypted connection bindings
└── CloudWatch logs/metrics
```

## Source components retained

Reuse or extract these proven components from the original repository:

- `lambda/agentcore/Dockerfile`: pinned all-CLI image pattern.
- `lambda/agentcore/cli/*`: headless Kiro, Claude, Codex, and OpenCode drivers and persistence adapters.
- `lambda/agentcore/workspace.js`: clone/reuse/restore behavior.
- `lambda/agentcore/git-auth.js`: temporary `GIT_ASKPASS` boundary.
- `lambda/agentcore/git-engine.js`: engine-owned commit/push/verification/merge.
- `lambda/agentcore/commands/init-ws.js`: deterministic intent workspace bootstrap.
- `lambda/agentcore/commands/lane.js`: lane checkout, branch, and merge lifecycle.
- `lambda/agentcore/stage-materializer.js`: prompt/rules/MCP projection into CLI-native configuration.
- `lambda/shared/agent-credential-grants.js`: signed, expiring grants.
- Source-control provider adapters and canonical repository validation.

Remove dependencies on Neptune, DynamoDB process state, Yjs, Cognito UI, and the Collaborative AI-DLC frontend from the extracted runner.

## Component design

### 1. KiroCrew app

The namespaced `collaborative-aidlc-kirocrew` app owns:

- integration onboarding and runtime health;
- intent creation/resume/status;
- local state and audit;
- agent/stage snapshot compilation;
- routing decisions;
- dispatch/cancel/resume;
- question and permission rendering;
- human gate recording;
- artifact/result ingestion.

It modifies no default agent, global steering, unrelated hooks, or unrelated skills.

### 2. Runtime provisioner

`ensure_runtime` is invoked during integration onboarding, before intent execution is enabled.

Inputs:

- AWS account and Region;
- network policy;
- pinned release manifest/image digest;
- source/model connection references;
- administrator confirmation receipt.

Behavior:

1. Discover an existing deployment by stable tags and deployment ID.
2. Compare runtime protocol, image digest, IAM policy revision, network mode, and broker revision.
3. Return healthy without mutation when compatible.
4. Otherwise show a deterministic change set and cost-bearing resources.
5. After explicit confirmation, deploy/update through one idempotent CloudFormation/CDK/Terraform entry point.
6. Poll runtime health and supported CLI capabilities.
7. Persist only deployment identifiers and non-secret status in KiroCrew.

Intent start performs a readiness check only; it never deploys infrastructure.

### 3. Shared runtime and session topology

One AgentCore runtime resource exists per KiroCrew integration environment.

Session IDs:

```text
Intent: aidlc-intent-<intent-id>
Lane:   aidlc-intent-<intent-id>-s<section>-<unit-slug>
```

- Serial stages use the Intent Session.
- Every concurrent unit uses its own Lane Session.
- Sessions use AgentCore persistent storage at `/mnt/workspace`.
- Parked sessions stop compute while retaining eligible storage.
- Missing/expired storage is restored from the durable remote branch.
- Runtime and session concurrency are bounded by policy and resource signals.

### 4. Assignment Snapshot Compiler

The compiler takes KiroCrew-local state and emits canonical JSON containing:

- intent, stage, unit, attempt, and revision identity;
- stage instructions and output contract;
- selected lead persona;
- methodology knowledge;
- resolved layered rules and project custom rules;
- compiled intent/unit context and attachments;
- selected CLI, model/tier, and routing rationale;
- normalized MCP/tool configuration;
- repository/provider/base/branch information;
- credential-grant references;
- timeout, budget, and idempotency key.

Canonical serialization is SHA-256 hashed. The snapshot and selected CLI are immutable for an assignment and its continuation.

Excluded by default:

- unrelated KiroCrew memory and lessons;
- local hooks;
- arbitrary global resources;
- local absolute paths;
- secret values;
- the user's complete Kiro/KiroCrew home.

### 5. CLI router

Default routing is deterministic data, not an LLM-only decision.

Inputs may include stage/role, unit kind, required capabilities, permitted models, organization policy, availability, cost class, and explicit user override.

Output:

```json
{
  "cli": "codex",
  "model": "openai.gpt-5.5",
  "reason": "code-generation default; required shell and MCP capabilities verified",
  "policyRevision": "..."
}
```

The route is visible before dispatch and recorded in the audit. Unsupported/unavailable routes fail closed; no CLI fallback is silent.

### 6. Credential authority

KiroCrew Connections owns user-facing setup, consent, status, and disconnect.

A minimal cloud broker preserves the original runtime protocol:

1. KiroCrew synchronizes an encrypted runtime-usable binding or provider installation reference during connection setup.
2. KiroCrew issues a short-lived signed grant naming customer, execution, project, provider, repository, access (`identity|read|write`), purpose, and expiry.
3. AgentCore redeems the grant with the broker.
4. The broker validates active execution, binding, repository membership, access capability, and expiry.
5. Git credentials exist only in a temporary `GIT_ASKPASS` environment around one Git operation.
6. Model credentials are vended by an equivalent assignment-scoped grant.

Supported source providers: GitHub, GitLab, Bitbucket, and CodeCommit.

### 7. Automatic workspace bootstrap

On first Intent Session invocation:

1. Validate repository identifiers and target paths.
2. Obtain a read grant.
3. Clone into the persistent workspace using argv-based Git with hooks disabled.
4. Scrub the remote to a credential-free URL.
5. Verify the expected base SHA.
6. Create the intent branch.
7. Handle empty repositories deterministically.
8. Push the intent branch through a write grant.
9. Return exact repository, base, branch, and SHA evidence.

On subsequent invocation, reuse the checkout. If absent, re-clone the durable branch before the CLI starts.

### 8. Lane execution

For each dependency-ready unit:

1. Allocate deterministic Lane Session ID.
2. Clone/fetch the remote intent branch.
3. Create or restore the unit branch.
4. Materialize the immutable assignment snapshot for the selected CLI.
5. Run the coding CLI headlessly.
6. Run declared checks.
7. Engine commits and pushes the branch.
8. Return exact SHA and normalized evidence.
9. KiroCrew verifies the result and invokes deterministic merge in DAG order.
10. Release the Lane Session after merge/terminal handling.

### 9. CLI materialization

| CLI         | Materialized runtime context                                       |
| ----------- | ------------------------------------------------------------------ |
| Kiro        | Workspace agent JSON, steering/rules, MCP entries, model           |
| Claude Code | Headless prompt, rules, MCP config, model, session identity        |
| Codex       | Private `CODEX_HOME`, config TOML, `AGENTS.md`, rules, MCP entries |
| OpenCode    | Inline configuration, instructions, MCP entries, model             |

Only the selected CLI's files are written. Runtime-only files are excluded from engine commits.

### 10. Assignment protocol

Request envelope fields:

```json
{
  "schemaVersion": 1,
  "assignmentId": "...",
  "idempotencyKey": "...",
  "sessionId": "...",
  "intent": {},
  "stage": {},
  "unit": {},
  "agentSnapshot": {},
  "routing": {},
  "source": {},
  "credentialGrants": {},
  "limits": {}
}
```

Result states:

- `SUCCEEDED`
- `WAITING_FOR_HUMAN`
- `WAITING_FOR_PERMISSION`
- `FAILED`
- `CANCELLED`
- `TIMED_OUT`

Every result carries assignment/session/snapshot identity, effective CLI/model, workspace/branch evidence, metrics, and typed errors. Success additionally carries commit SHA, changed paths, checks, artifacts, and push verification.

### 11. Human interaction bridge

A remote question/permission returns a parked result and continuation token. KiroCrew:

1. persists it against the local attempt/revision;
2. renders it in the originating session/channel;
3. authorizes answers from permitted participants;
4. records actor, authorization basis, timestamp, and decision;
5. resumes the same AgentCore session and CLI conversation;
6. restores from durable branch/context if the session expired.

No timeout or transport error becomes approval.

### 12. Local state and audit

KiroCrew remains authoritative for:

- intent and stage status;
- dependency DAG and ready queue;
- agent snapshot hashes;
- routing decisions;
- assignments and AgentCore sessions;
- results and verification;
- reviewer verdicts;
- human questions/gates;
- retries, requeues, cancellation, and completion.

State transitions use compare-and-set revision/attempt identities and are replay safe.

## Security design

- Customer-owned AWS account and VPC-by-default runtime networking.
- Non-root digest-pinned runner image with software inventory.
- No source/model secret in Agent Snapshot, argv, remote URL, repository config, logs, or result.
- Signed short-lived grants scoped to one assignment/purpose.
- Repository hooks disabled for engine Git.
- Runtime paths excluded from commits.
- KiroCrew verifies returned ancestry, protected paths, checks, and exact SHA before accepting/merging.
- Compatibility failures are typed and fail closed.
- Infrastructure changes require explicit administrator confirmation.

## Failure and recovery

| Failure                     | Recovery                                                                |
| --------------------------- | ----------------------------------------------------------------------- |
| Runtime absent/incompatible | Keep intents disabled; run idempotent onboarding repair                 |
| CLI unavailable             | Reject route before repository mutation                                 |
| Credential expired          | Renew grant; do not switch credential source silently                   |
| Clone/base mismatch         | Fail assignment; require binding/base correction                        |
| Session storage expired     | Re-clone durable branch and reconstruct snapshot                        |
| CLI crash/timeout           | Preserve/push recoverable work, return typed result, requeue locally    |
| Push failure                | Retry with backoff; fail if new work is not durable                     |
| Merge conflict              | Run scoped conflict flow; never leave integration workspace dirty       |
| KiroCrew restart            | Reload local assignment/session mappings and reconcile AgentCore status |
| Duplicate invocation        | Resolve from idempotency record without repeating side effects          |

## Observability

KiroCrew displays:

- runtime deployment/readiness and image digest;
- active Intent/Lane Sessions;
- stage/unit/attempt/revision;
- selected CLI/model and routing rationale;
- agent snapshot hash;
- clone/branch/commit/push/merge evidence;
- checks and reviewer/gate state;
- duration, tokens/credits, and cost when reported;
- typed failure and recovery action.

CloudWatch retains execution-plane logs and metrics with credential redaction.

## Testing strategy

1. Pure contract tests for canonical snapshots, hashes, routing, session IDs, branch names, and idempotency.
2. Per-CLI invocation/materialization tests.
3. Credential-grant authorization and redaction tests.
4. Local Git remote tests for clone, empty repository, resume, lane, push, merge, and conflict.
5. AgentCore integration tests for session persistence, park/resume, stop/restart, and storage recovery.
6. Cross-CLI end-to-end tests: Kiro, Claude, Codex, OpenCode.
7. Mixed-lane test with at least two CLIs running concurrently and deterministic merge.
8. KiroCrew restart/reconciliation and human-gate tests.
9. Infrastructure plan, least-privilege, update, rollback, and teardown tests.

## Requirement traceability

| Requirements | Design components                           |
| ------------ | ------------------------------------------- |
| R1, R13      | KiroCrew app, onboarding                    |
| R2, R12      | Runtime provisioner, observability          |
| R3, R7       | Runner image, CLI router                    |
| R4           | Assignment Snapshot Compiler, materializers |
| R5           | Credential authority, workspace bootstrap   |
| R6           | Session topology, lane execution            |
| R8           | Git engine, result verification             |
| R9           | Human interaction bridge                    |
| R10          | Assignment protocol, local state            |
| R11          | Security design                             |
