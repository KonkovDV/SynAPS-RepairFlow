# SynAPS RepairFlow agent bus

RepairFlow coordinates implementation work through GitHub issues and pull requests. The issue is the queue, one structured comment is the live status, and the pull request is the only place where code changes are made.

The protocol is `synaps.agent_bus.v1`. It is intentionally repository-local: AeroBIM's bus cannot attest SynAPS URLs or SynAPS CI jobs.

## Bootstrap rule

The first bootstrap pull request establishes this protocol. It may be opened from issue #4 without a prior machine-validated claim. Once this PR is merged, every later implementation phase must have a valid claim before creating a branch.

## Lifecycle

1. Create or select one open issue for exactly one phase.
2. Read the issue and all comments.
3. Record one `claim` object before branch work. The claim records the current `main` SHA, feature branch, agent, host, and timezone-aware lease.
4. Send `heartbeat` at least every six hours while the PR is not green.
5. Use `blocked` when a dependency prevents progress; include blocking issue numbers.
6. Use `handoff` to release work without declaring completion.
7. Use `done` only after the PR is merged and the cited CI run is completed successfully.

There is one open PR per issue. Never push to `main`, reuse another agent's branch, or call a local test run CI evidence.

## Comment format

```markdown
### AGENT_BUS synaps.agent_bus.v1
```json
{
  "schema": "synaps.agent_bus.v1",
  "op": "claim",
  "issue": 4,
  "agent": "repairflow-session",
  "host": "cloud",
  "base_sha": "76d09467fc60",
  "branch": "feat/4-agent-bus-bootstrap",
  "until": "2026-10-01T06:00:00+03:00"
}
```
```

Supported operations are `claim`, `heartbeat`, `blocked`, `handoff`, `steal`, and `done`. The validator checks the first live claim, expiry, holder identity, branch binding, and CI evidence.

## CI attestation

The current PR gate consists of:

- `lint`
- `test-fast`
- `synaps-pin`
- `demo-evidence`
- `benchmark`

`test-slow` runs only on pushes to `main`; it is not a PR gate. A green run must be completed successfully, contain every required job, report a non-zero `runner_id` and non-empty `runner_name`, and contain at least one successful step per required job. The Jobs API payload is the evidence source for runner fields.

`done` must cite the real SynAPS PR URL, Actions run URL, and a SHA that is the run's `head_sha`. The local command `pytest` never becomes a CI pin.

## Product boundary

Bus comments coordinate work; they do not issue the product verdict. Validator rejects `summary_passed`, `verified`, `customer_go`, `deployment_go`, accuracy claims, customer claims, and similar product-gate fields. Only RepairFlow's evidence and verdict code may set `verified_feasible`, status, exit code, or pilot gates.

## Commands

```bash
python tools/agent_bus.py check-comment comment.md
python tools/agent_bus.py check-run run.json jobs.json
python tools/agent_bus.py check-thread 4 comments.json
python tools/agent_bus.py check-done 4 comments.json run.json jobs.json
python tools/agent_bus.py check-steal 4 comments.json compare.json
```

The validator is deterministic and offline. It does not call GitHub.
