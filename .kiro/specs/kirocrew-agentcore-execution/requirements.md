# Requirements: KiroCrew-managed AgentCore execution plane

## Status

- Phase: Complete
- Product direction: Hybrid execution
- Control plane: KiroCrew local
- Execution plane: Amazon Bedrock AgentCore
- Source baseline: `aws-samples/sample-collaborative-ai-dlc`
- Open decisions: None

## Problem

Customers should use KiroCrew as the released and supported experience for Collaborative AI-DLC. KiroCrew should retain local intent state, agents, skills, memory, scheduling, reviews, and human gates while delegating coding work to isolated, elastic AgentCore sessions. Customers must not manually provision Remote Crews, install coding CLIs on hosts, clone repositories, create unit branches, or maintain long-running containers.

## Confirmed source behavior

The original implementation establishes these lifecycle facts:

1. Terraform builds one digest-pinned ARM64 image containing Kiro CLI, Claude Code, OpenCode, Codex, Git, Bun, and supporting tools.
2. Terraform creates one AgentCore runtime resource from that image during platform deployment, before any intent starts.
3. Starting an intent invokes the existing runtime with a deterministic `runtimeSessionId`; it does not build an image or deploy a runtime.
4. AgentCore creates or resumes the session microVM and persistent `/mnt/workspace` mount on demand.
5. `init-ws` deterministically clones repositories, creates/checks out the intent branch, and publishes it before stage execution.
6. Temporary source-control credentials are exposed only to Git subprocesses through `GIT_ASKPASS`; clean remotes contain no credential.
7. The same session ID keeps the checkout warm across stages. Missing or expired workspace storage is recloned automatically.
8. Parallel unit lanes receive isolated sessions/workspaces and branches derived from the remote intent branch.
9. Runtime code—not the coding agent—commits, pushes, verifies, and merges work.
10. The selected CLI is resolved at runtime from the same all-harness image.

## Chosen lifecycle default

The hybrid implementation SHALL preserve the distinction between **runtime deployment** and **intent execution**:

- One AgentCore **runtime resource** (image + IAM + network + lifecycle configuration) is shared by a deployment/environment.
- Each active intent gets its own deterministic **Intent Session**, which means its own isolated microVM execution context and persistent workspace mount.
- Each concurrent construction unit gets its own deterministic **Lane Session**, distinct from the Intent Session and from sibling units.
- Many intent and lane sessions MAY run concurrently on the shared runtime resource; this is how one human or team drives several intents and unit lanes at once.
- KiroCrew SHALL provision the shared runtime transparently during integration onboarding, before **Start Intent** is enabled.
- KiroCrew SHALL show one infrastructure-change confirmation, deploy the pinned image/runtime/IAM resources, and verify readiness as part of that onboarding.
- Intent start SHALL perform no infrastructure deployment; it only creates or resumes Intent and Lane Sessions on the existing runtime.
- Every intent/unit SHALL allocate or reuse an AgentCore runtime session on demand.
- Image/runtime updates SHALL occur during adapter update or explicit runtime maintenance—not once per intent.

This matches the original deployment model while removing a separate manual installation workflow.

## Glossary

- **KiroCrew Control Plane**: Local KiroCrew gateway, app, state, agents, skills, memory, scheduler, approvals, and UI.
- **Execution Plane**: Shared AgentCore runtime and its on-demand runtime sessions.
- **Runner Image**: Digest-pinned image containing all supported coding CLIs and deterministic workspace/Git code.
- **Agent Snapshot**: Immutable, hashed projection of a KiroCrew agent and its eligible context for one remote assignment.
- **Intent Session**: AgentCore runtime session used for serial intent stages and persistent checkout.
- **Lane Session**: AgentCore runtime session used for one unit-of-work lane.
- **Credential Grant**: Short-lived, narrowly scoped authorization used by runtime code to obtain model or source-control credentials.
- **Assignment Envelope**: Versioned request sent by KiroCrew to AgentCore.
- **Assignment Result**: Structured completion, failure, question, permission, or continuation response returned to KiroCrew.

## Requirements

### R1. KiroCrew remains the customer experience

**User story:** As a customer, I want to create, steer, approve, and inspect Collaborative AI-DLC intents from KiroCrew so I do not need another custom tool.

#### Acceptance criteria

1. WHEN the integration is installed THEN KiroCrew SHALL expose intent creation, status, questions, approvals, artifacts, worker activity, cancellation, retry, and completion through existing KiroCrew surfaces.
2. KiroCrew SHALL remain the authoritative store for local intent state, dependency scheduling, agent selection, human decisions, and audit records.
3. The execution plane SHALL not require the Collaborative AI-DLC React frontend, CloudFront distribution, Cognito UI, Yjs collaboration service, Neptune graph, or DynamoDB workflow store.
4. The integration SHALL remain namespaced and removable without modifying the user's default KiroCrew agent, hooks, steering, or unrelated skills.

### R2. Runtime provisioning is transparent and reusable

**User story:** As a customer, I want KiroCrew to make remote execution available automatically so I do not manually deploy or maintain worker containers.

#### Acceptance criteria

1. WHEN an administrator connects the integration to an AWS account/Region THEN KiroCrew SHALL call `ensure_runtime` during onboarding, before enabling intent execution.
2. IF no compatible runtime exists THEN KiroCrew SHALL present one explicit infrastructure-change confirmation containing account, Region, image digest, resources, estimated ongoing cost, and teardown path.
3. WHEN confirmed THEN KiroCrew SHALL deploy the ECR image, AgentCore runtime, IAM roles/policies, logging, networking configuration, and credential-broker resources as one idempotent operation.
4. WHEN deployment completes THEN KiroCrew SHALL verify runtime health/capabilities and enable **Start Intent**.
5. WHEN an intent starts THEN KiroCrew SHALL verify the compatible runtime remains ready but SHALL NOT deploy infrastructure.
6. No intent SHALL build an image, register a runtime, or create a manually maintained Remote Crew.
7. Runtime updates SHALL be digest-pinned, idempotent, observable, and independently reversible.

### R3. One image supports all coding CLIs

**User story:** As an administrator, I want one managed runner image to support all approved coding tools so backend selection does not require separate hosts.

#### Acceptance criteria

1. The image SHALL install pinned, verified versions of Kiro CLI, Claude Code, Codex, OpenCode, Git, and required ACP/native adapters.
2. Image builds SHALL verify downloaded artifacts by digest or package lock and emit a software inventory.
3. An assignment SHALL select its CLI through the envelope; image selection SHALL not depend on the CLI.
4. An unavailable or incompatible CLI SHALL fail before repository mutation and SHALL not silently fall back to another CLI.
5. KiroCrew SHALL expose runtime-reported CLI versions and capabilities before assignment.

### R4. KiroCrew agents are inherited through immutable snapshots

**User story:** As a user, I want remote workers to use my selected KiroCrew agent, skills, and approved context without installing those agents in the image.

#### Acceptance criteria

1. Before dispatch, KiroCrew SHALL compile a bounded execution snapshot containing the selected agent identity/persona, stage instructions, methodology knowledge, resolved layered rules, project custom rules, compiled intent/unit context, attachments, model/tier selection, tool contract, and normalized MCP declarations.
2. The snapshot SHALL have a canonical content hash and SHALL be pinned for the assignment/session.
3. The runtime SHALL materialize only the selected CLI's native configuration without changing the snapshot's semantics silently.
4. Unsupported local paths, hooks, tools, MCP transports, or secrets SHALL be reported before execution with a typed compatibility result.
5. Secret values SHALL never be embedded in the snapshot; only approved opaque references or short-lived grants may cross the boundary.
6. Unrelated KiroCrew memory, lessons, hooks, global resources, and the user's complete local agent home SHALL remain local unless a future requirement maps them explicitly.
7. The Assignment Result SHALL report the snapshot hash, effective CLI/model, and any compatibility exceptions.

### R5. Repository checkout is automatic

**User story:** As a user, I want the remote runner to prepare its repository automatically so no host checkout is required.

#### Acceptance criteria

1. The Assignment Envelope SHALL identify source provider, repository, expected base branch/SHA, intent branch, and required access.
2. On the first invocation of an Intent Session, deterministic runtime code SHALL clone the repository before starting a coding CLI.
3. Clone URLs and repository configuration SHALL remain credential-free at rest.
4. KiroCrew Connections SHALL own the user-facing source-control setup, consent, and health status; the user SHALL NOT configure a duplicate Collaborative AI-DLC connection.
5. A minimal cloud credential broker SHALL preserve the original signed grant and redemption contract, including active-execution, project, repository, provider, required-access, expiry, and committer-identity checks.
6. Source-control credentials SHALL be short-lived, scoped to the repository and operation, and exposed only around Git network subprocesses through temporary `GIT_ASKPASS` state.
7. The runtime SHALL verify the expected base SHA before creating the intent branch.
8. It SHALL create and publish the intent branch automatically.
9. If persistent session storage is missing or expired, the runtime SHALL re-clone the last durable branch and report workspace restoration.
10. Empty repositories and multiple repositories SHALL follow the original implementation's deterministic initialization behavior.

### R6. Unit lanes are provisioned automatically

**User story:** As a user, I want dependency-ready units to run in isolated remote workspaces without manually creating containers or branches.

#### Acceptance criteria

1. KiroCrew SHALL compute dependency-ready units from its local approved DAG.
2. Each dispatched unit SHALL receive a deterministic Lane Session ID and unit branch.
3. A fresh lane SHALL automatically clone the remote intent branch and create/publish its unit branch.
4. A retried lane SHALL resume its durable branch/session when valid and SHALL re-clone when the workspace is unavailable.
5. Independent units MAY run concurrently; dependent units SHALL wait for their provider units to be verified and merged.
6. KiroCrew SHALL enforce configured concurrency, timeout, cancellation, and budget limits without requiring persistent user-managed workers.

### R7. Mixed coding agents are first-class

**User story:** As a user, I want different stages or units to use the best approved coding CLI while preserving one lifecycle and audit trail.

#### Acceptance criteria

1. Every assignment SHALL carry an explicit CLI or a deterministic routing decision recorded by KiroCrew.
2. Dependency-ready assignments MAY select different CLIs while using the same runner image and AgentCore runtime resource.
3. Routing MAY consider stage/role, unit kind, requested model, capability requirements, policy, cost, and user override.
4. The selected CLI SHALL be pinned for the assignment and continuation.
5. A human SHALL be able to inspect and override routing before dispatch when policy requires it.
6. Results from all CLIs SHALL normalize into the same Assignment Result contract.

### R8. Runtime Git operations are engine-owned

**User story:** As a user, I want remote work to be durable and safely integrated regardless of which coding CLI produced it.

#### Acceptance criteria

1. Coding agents SHALL not receive source-control credentials.
2. Runtime code SHALL inspect the working tree, apply runtime-file exclusions, commit with deterministic attribution, and push the assigned branch.
3. Results SHALL include exact base SHA, commit SHA, changed paths, test evidence, and push-verification status.
4. KiroCrew SHALL verify ancestry, scope, protected-state paths, and test evidence before accepting a result.
5. Unit branches SHALL be merged in dependency order by deterministic integration code, not by an LLM.
6. Conflicts SHALL produce a scoped conflict result and SHALL not leave the integration workspace dirty.

### R9. Questions, permissions, and gates round-trip through KiroCrew

**User story:** As a user, I want remote work to pause and continue through normal KiroCrew interactions.

#### Acceptance criteria

1. A remote worker needing human input SHALL return `WAITING_FOR_HUMAN` with a structured question or permission request and continuation identity.
2. KiroCrew SHALL persist the pending request locally and render it through its existing approval/question surfaces.
3. The answer SHALL resume the same AgentCore session, checkout, branch, Agent Snapshot, and CLI conversation when still valid.
4. Parked compute SHALL be released where supported without deleting persistent session storage.
5. Expired sessions SHALL restore from the durable branch and explicit continuation context rather than silently restarting the stage.
6. No remote worker SHALL infer approval from timeout, silence, or transport failure.

### R10. Protocols are versioned and idempotent

#### Acceptance criteria

1. Assignment Envelope and Assignment Result SHALL carry schema versions and idempotency keys.
2. Retrying an invocation SHALL not create duplicate branches, commits, questions, or completion records.
3. Runtime session IDs, branch names, and assignment IDs SHALL be deterministic from intent/stage/unit identity where appropriate.
4. KiroCrew SHALL reject unsupported runner/protocol versions before dispatch.
5. Every state-changing response SHALL be safe to replay or shall carry a compare-and-set token.

### R11. Security boundaries are explicit

#### Acceptance criteria

1. The runtime IAM role SHALL use least privilege and SHALL not inherit the local KiroCrew process's ambient credentials.
2. Agent snapshots and logs SHALL be scanned/redacted for credentials before persistence or delivery.
3. The runner image SHALL run non-root and use AgentCore session isolation.
4. Repository hooks SHALL not execute during engine-owned Git operations.
5. Runtime and credential grants SHALL be scoped to one customer, intent, repository, purpose, and expiry.
6. The system SHALL produce an auditable record of image digest, runtime version, CLI, model, agent hash, credential source, Git SHA, tests, and human decisions.

### R12. Observability and lifecycle management

#### Acceptance criteria

1. KiroCrew SHALL show deployment state, runtime readiness, active sessions, stage/unit progress, selected CLI, elapsed time, usage/cost when available, and terminal result.
2. Failures SHALL distinguish provisioning, authentication, clone, compatibility, CLI, test, push, merge, timeout, cancellation, and restore errors.
3. Runtime sessions SHALL have idle and maximum-lifetime policies; stopping a session SHALL not delete durable work.
4. KiroCrew SHALL provide explicit runtime update, diagnose, and teardown actions.
5. Teardown SHALL identify resources and retained source branches before deletion.

### R13. Customer setup is minimal

#### Acceptance criteria

1. A new customer SHALL install the namespaced KiroCrew app and connect an AWS account/Region plus source-control/model credentials.
2. Integration onboarding SHALL transparently deploy and verify the shared runtime after one explicit infrastructure confirmation.
3. **Start Intent** SHALL remain disabled until a compatible runtime is ready.
4. Starting any intent SHALL require no deployment, CLI installation, host registration, repository clone, or branch setup.
5. The normal path SHALL require no KiroCrew Remote Crew configuration.

## Non-goals

1. Reusing the Collaborative AI-DLC frontend.
2. Requiring the full Neptune/DynamoDB/Yjs/Cognito application backend.
3. Copying the user's entire `~/.kiro` or KiroCrew data home into AgentCore.
4. Keeping idle per-CLI containers or manually managed remote gateways.
5. Letting coding agents own Git credentials or integration merges.
6. Claiming exact semantic compatibility for unsupported agent resources.

## Resolved decisions

### Q1. Runtime ownership — resolved

**Decision: A.** The shared AgentCore runtime runs in the customer's AWS account, matching the original sample. KiroCrew automates deployment and lifecycle after explicit infrastructure confirmation.

### Q2. Provisioning interaction — resolved

**Decision: B.** Match the original lifecycle: integration onboarding deploys and verifies the shared runtime before **Start Intent** is enabled. The process is automated by KiroCrew after one infrastructure confirmation; intent start itself never deploys infrastructure.

### Q3. Source-control credential authority — resolved

**Decision: D.** KiroCrew Connections owns setup, consent, and status. A minimal cloud broker stores/redeems the runtime-usable binding and preserves the original signed grant, execution/repository/access checks, provider adapters, temporary `GIT_ASKPASS`, invalidation, and committer attribution. The user configures one connection, not two.

### Q4. Supported source providers — resolved

**Decision: C.** Preserve the original coverage: GitHub, GitLab, Bitbucket, and CodeCommit.

### Q5. Agent Snapshot contents — resolved

**Decision: match the original materialization contract.** KiroCrew compiles a canonical execution snapshot containing the stage instructions, selected lead persona, methodology knowledge, resolved layered rules, project custom rules, compiled intent/unit context, attachments, model/tier selection, and normalized MCP/tool configuration. The runner materializes only the selected CLI's native configuration. It does not copy unrelated KiroCrew memory, hooks, global resources, or the user's full local agent home unless a later requirement explicitly maps them.

### Q6. Mixed-CLI routing — resolved

**Decision: C.** KiroCrew applies a deterministic policy/default route using stage/role, unit kind, capability requirements, policy, model availability, and cost signals. The selected CLI and rationale are visible before dispatch, and an authorized human may override it. The chosen CLI is pinned for that assignment and its continuation.

### Q7. Session topology — resolved

**Decision: A.** Match the original topology: one deterministic Intent Session for serial stages plus one deterministic Lane Session per concurrent `(intent, section, unit)`. All sessions run on the one shared runtime resource and may execute concurrently within configured limits.

### Q8. Git integration authority — resolved

**Decision: A.** Preserve engine-owned commit, push, verification, and deterministic merge behavior. Coding CLIs never receive source-control credentials.

### Q9. Model authentication — resolved

**Decision: A.** Preserve customer-managed Kiro API key plus Bedrock API key semantics. KiroCrew owns setup/status and stores opaque references; the minimal cloud broker vends assignment-scoped credentials to AgentCore without embedding values in the Agent Snapshot.

### Q10. Networking — resolved

**Decision: B.** Preserve VPC-by-default AgentCore networking, including private runtime subnets and controlled egress through NAT or approved private endpoints. Public mode is not the default.

### Q11. Multi-user approvals — resolved

**Decision: B.** Gates may be answered by authorized users in the originating KiroCrew session/channel. Every answer records actor identity, authorization basis, timestamp, and decision. Named quorum policy is deferred.

### Q12. Runtime teardown — resolved

**Decision: A.** The shared runtime remains until explicitly removed or replaced. Intent/Lane Sessions stop on park, idle timeout, cancellation, or completion while durable Git work and eligible session storage follow retention policy.

## Requirements-session exit status

Requirements are complete: Q1–Q12 are resolved and reflected in the acceptance criteria. The specification is ready for design and task decomposition.
