# Managing mixed coding-agent crews

Use this procedure when one Collaborative AI-DLC intent needs work from Kiro, Claude Code, Codex, or OpenCode specialists without leaving the KiroCrew experience.

## What parity means

Collaborative AI-DLC currently selects and pins one CLI for an intent. A dedicated KiroCrew gateway with a backend frozen for the intent approximates that model, with backend-specific capability differences validated before execution. KiroCrew does not reproduce the source platform's engine-owned git or immutable CLI binding.

A mixed Remote Crew fleet adds an optional manual pattern: one hub dashboard supervises conversations whose tools, model, and workspace run on gateways configured for different harnesses. In KiroCrew 0.8, **New chat on crew** is a feature preview; `spawn_run` cannot target a Remote Crew or override its backend. The conductor must not describe cross-host dispatch as automatic.

## Reference topology

```text
KiroCrew hub dashboard and conductor
├── crew-kiro      → Kiro CLI backend
├── crew-claude    → Claude Code + claude-agent-acp
├── crew-codex     → codex-acp
└── crew-opencode  → OpenCode ACP
```

Each execution host owns its gateway, coding-agent login, agent specs, repository checkout, sandbox, approvals, model, and tools. A **New chat on crew** conversation row, transcript, history, and search record remain on the hub; execution and workspace access happen remotely. Do not copy provider credentials between hosts.

## 1. Prepare each execution host

On every host:

1. Install KiroCrew 0.8 or later and start its gateway on loopback (default port `5476`).
2. Clone the same source repository and check out the approved base branch.
3. Install this adapter on that host:

```bash
cd /path/to/sample-collaborative-ai-dlc/kirocrew-collaborative-aidlc
python3 scripts/validate_bundle.py
kirocrew app install "$(pwd)"
kirocrew app enable collaborative-aidlc-kirocrew
```

4. Install and authenticate the host's chosen coding harness.
5. Select the backend under **Settings → Developer → Agent Backend**, restart the gateway, and run `kirocrew doctor`.
6. Keep that backend unchanged until the assigned work is complete. A mid-intent backend switch is not an immutable CLI pin.

### Backend-specific setup

| Crew        | Host prerequisites                                                                                                                                                                                        | Select backend                                   |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Kiro CLI    | Install `kiro-cli` and sign in on that host. KAS uses the same binary with a supported v3 engine.                                                                                                         | Choose **Kiro CLI** or **KAS** in the dashboard. |
| Claude Code | Install and authenticate the Claude Code CLI, then install its ACP adapter: `npm i -g @agentclientprotocol/claude-agent-acp`. Both `claude` and the adapter must resolve in the gateway service's `PATH`. | `kirocrew config set agent.acp_backend claude`   |
| Codex       | Install the ACP adapter: `npm i -g @agentclientprotocol/codex-acp`. It carries a compatible Codex dependency; complete the Codex authentication flow on that host before unattended use.                  | `kirocrew config set agent.acp_backend codex`    |
| OpenCode    | Install `npm i -g opencode-ai`, configure its model provider, and authenticate on that host. OpenCode serves ACP directly.                                                                                | `kirocrew config set agent.acp_backend opencode` |

After a CLI or adapter install:

```bash
kirocrew restart
kirocrew doctor
```

If `doctor` reports a binary missing even though it works in an interactive shell, fix the gateway service's `PATH`; shell startup files do not automatically reach launchd or systemd services.

### Validate the remote roster and capability surface

The remote roster wins; hub agents are not copied into a remote session. Before assigning real work on every host:

1. Confirm `collaborative-aidlc-conductor` and every specialist/reviewer needed on that host appears in its agent selector.
2. Open an authenticated smoke chat on that host, bind the intended checkout, and verify file read, an approved file write, shell/test execution where required, and the KiroCrew control-plane tools used by the role.
3. Confirm the selected model is available and record any backend-specific limitation in the intent evidence.
4. Refuse or reassign a stage when its required tool restrictions, MCP servers, reviewer role, or resume behavior cannot be proven on that harness.

The goal is one lifecycle contract across crews, not a claim that every harness implements identical capabilities.

## 2. Connect the hosts to one hub

On the KiroCrew installation participants already use:

```bash
kirocrew config set instances.enabled true
kirocrew restart
```

Then open **Settings → Remote Crew** and add one record per host.

### SSH

Provide:

- **Name**: include the harness, such as `AIDLC – Claude`.
- **SSH host / alias**: exactly what works with noninteractive `ssh`, including any `ProxyJump` in `~/.ssh/config`.
- **Remote port**: the remote gateway port, normally `5476`.
- **Token TTL**: the minted dashboard-token validity, `20h` by default. Keep the default unless policy requires another value; this is not an intent execution timeout.
- **Remote KiroCrew path**: only when `kirocrew` is not on the remote command path.

### AWS Systems Manager

The hub needs the AWS CLI and Session Manager plugin. The remote must be an SSM Online managed instance with SSM Agent and a managed-instance/EC2 role. Register its target, AWS profile, Region, and `ssm_run_as` POSIX user; that user must own the running gateway and its KiroCrew/Kiro homes (`ec2-user` is the default, while Ubuntu commonly uses `ubuntu`).

The hub identity needs at least `ssm:StartSession`, `ssm:SendCommand`, and `ssm:GetCommandInvocation`; add `ssm:DescribeInstanceInformation` when Diagnose/readiness discovery requires it. Scope `StartSession` and `SendCommand` to the intended target and SSM document ARNs. KiroCrew 0.8's reference IAM policy keeps `GetCommandInvocation` and `DescribeInstanceInformation` on `Resource: "*"` because those reads are not usefully resource-scoped; constrain principals and conditions instead. No inbound port is required.

SSM token minting uses `SendCommand`. Its command output can retain the minted dashboard token for up to 30 days and expose it to principals allowed to call `GetCommandInvocation`; the token TTL and loopback-only endpoint limit its use but do not make that history secret-free. Restrict command-history access, use the shortest practical token TTL, and follow your account's SSM output-retention controls.

Click **Connect** for every crew. Enable **Settings → Developer → Feature Previews → Chat on a crew**. The KiroCrew header becomes the switcher for these preview sessions. The tunnel must remain recoverable; a remote turn already in flight can continue if the hub restarts, while the hub-owned transcript records that interruption.

Before marking real work `running`, create one disposable **New chat on crew** from the hub for every remote. Confirm version compatibility, remote agents/models/workspaces in the picker, execution in the intended remote checkout, tool approvals, and transcript delivery back to the hub. A direct smoke chat opened on the remote host is useful but does not prove this hub-mediated path.

## 3. Prepare source-control lanes

Use sibling Git refs; a ref cannot also be the parent directory of another ref:

```text
aidlc/<intent-slug>-integration
aidlc/<intent-slug>--unit-<unit-slug>-kiro
aidlc/<intent-slug>--unit-<unit-slug>-claude
aidlc/<intent-slug>--unit-<unit-slug>-codex
aidlc/<intent-slug>--unit-<unit-slug>-opencode
aidlc/<intent-slug>--support-<role>-<harness>
```

Create every unit/support branch from the exact current integration SHA and record that expected base. A remote crew owns only its assigned branch. Protect the integration branch and conductor-state paths from remote push credentials where the source-control system supports it.

Never let two crews write the same branch. Support sessions should be analysis-only by default; if they must write, give each a separate support branch and have the unit owner integrate a reviewed, pinned commit.

## 4. Keep one conductor authoritative

Run `collaborative-aidlc-conductor` on the hub or one designated Remote Crew. Only that session may:

- run `workflow.py` state-transition commands;
- update `workflow-state.json`, `aidlc-state.md`, active selectors, ownership marker, or audit records;
- register the unit DAG;
- record reviewer verdicts and human gate decisions;
- merge completed branches into the integration branch.

Remote specialist sessions may write declared artifacts and source code, run tests, and commit their assigned branches. They must never advance workflow state.

## 5. Assign dependency-ready work

On the conductor host:

```bash
python3 "$RUNNER" --project "$PROJECT" status --json
python3 "$RUNNER" --project "$PROJECT" context \
  --stage "$STAGE" [--unit "$UNIT"]
```

The context uses paths relative to `projectRoot`, so the remote may use a different absolute checkout directory. Confirm those relative paths resolve inside the selected remote checkout before sending the task.

Assign only entries returned in `current`. The walking skeleton is first; later units become eligible only after dependencies are approved and merged.

For each assignment:

1. Create and push the unit branch from the recorded integration SHA.
2. Connect/open the target crew and verify its remote checkout and specialist agent are ready.
3. Immediately before handing off, mark the stage running:

```bash
python3 "$RUNNER" --project "$PROJECT" start \
  --stage "$STAGE" [--unit "$UNIT"]
```

4. In the hub dashboard choose **New chat on crew** and select the Kiro, Claude, Codex, or OpenCode crew.
5. Bind the chat to that remote checkout and select the specialist named by `runtimeLead`.
6. Paste the generated context JSON, expected base SHA, branch name, and remote project root. Require work only on this stage/unit, declared outputs, relevant checks, a commit/push, and a returned commit SHA plus evidence.
7. Run support roles as analysis-only conversations or separate support branches; never share the unit branch across hosts.

Different dependency-ready units may run concurrently on different harnesses. A stage/unit returned alone stays serialized.

If dispatch fails after `start`, return it to revising before reassignment:

```bash
python3 "$RUNNER" --project "$PROJECT" requeue \
  --stage "$STAGE" [--unit "$UNIT"] \
  --reason "<crew unavailable or handoff failed>"
```

Regenerate context after `requeue`; its attempt/revision and feedback changed.

## 6. Reconcile each result safely

When a remote crew returns `<remote-ref>`, `<expected-base>`, and `<commit-sha>`, the conductor:

1. Fetches the explicit ref without executing code from it.
2. Verifies the SHA is the fetched tip and descends from the expected base:

```bash
git fetch origin "+refs/heads/<remote-ref>:refs/remotes/origin/<remote-ref>"
test "$(git rev-parse "origin/<remote-ref>")" = "<commit-sha>"
git merge-base --is-ancestor "<expected-base>" "<commit-sha>"
```

3. Reviews exactly `<expected-base>...<commit-sha>`. Reject unapproved merge commits, unrelated history, out-of-scope paths, and changes to conductor-owned state: `workflow-state.json`, `aidlc-state.md`, `active-space`, `active-intent`, `.kirocrew-collaborative-aidlc.json`, and `audit/events.jsonl`.
4. Runs tests in a clean worktree at the exact SHA. Treat remote test claims as evidence to reproduce, not proof.
5. Merges or cherry-picks only the reviewed SHA into the integration branch, in deterministic DAG order, then reruns integration checks.
6. Runs `finish` only after the code and artifacts are present on the integration branch.
7. Opens a clean-room reviewer session on the desired crew. Give it artifacts, exact diff, and test evidence—not the author transcript.
8. Records the reviewer verdict, presents the human gate, and records only the explicit human decision.
9. Reads `status --json` again before assigning more work.

Do not merge a dependent unit before its provider. Do not complete a stage while its result exists only on an unmerged remote branch.

## 7. Recover or rebalance

If a crew becomes unavailable:

1. If the state is `running`, use `requeue` with the failure reason.
2. Push any recoverable branch work from that host without changing the recorded expected base.
3. Inspect partial side effects before retrying.
4. Open the branch at its exact reviewed SHA on another crew and regenerate context.
5. Re-run capability smoke checks and tests because the harness/environment changed.
6. Record the replacement crew, backend, final SHA, and evidence.

If a backend cannot honor a required capability, reassign before execution; never silently broaden tools or downgrade a review.

## Operating rules

- One KiroCrew hub remains the participant experience; Chat on a crew is explicitly a preview in 0.8.
- One conductor owns state, integration, and gates.
- One branch owner per unit; support writers get separate branches.
- Only dependency-ready units run in parallel.
- Credentials stay local to each crew.
- Every handoff includes expected base, remote ref, exact commit SHA, artifact paths, test commands, and results.
- Every returned SHA is ancestry-checked, path-reviewed, and retested before integration.
- Human approval remains central even when implementation is distributed.
