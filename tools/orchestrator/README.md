# Devin OSV Remediation Orchestrator

Automated PyPI vulnerability remediation for Apache Superset: `osv-scanner` detects, the Devin v3 API remediates, GitHub Actions glues it together.

## Flow

```
       cron               issues.opened             api.devin.ai
osv-scanner ─────► Issue ───────────────► Devin session ───────► PR
                    ▲                                              │
                    │             ┌────────────────────────────────┘
                    │             ▼
                    │     "Closes #N" auto-closes Issue
                    │
            tools/orchestrator/STATUS.md (regenerated after every run)
```

The orchestrator covers detection, Issue templating, dedup, and Devin session lifecycle (create, message, poll). The code change — locating the source constraint, running `scripts/uv-pip-compile.sh`, handling pre-commit's auto-edits, writing the PR body — is delegated to Devin.

## Components

| Path | Purpose |
|---|---|
| `.github/ISSUE_TEMPLATE/osv-finding-pypi.md` | OSV finding schema and remediation playbook embedded into every Issue |
| `.github/workflows/osv-scan.yml` | Daily cron (03:00 JST) + `workflow_dispatch`. Runs `orchestrator scan` |
| `.github/workflows/osv-remediate.yml` | `issues.opened` (filtered to `osv-finding` label) + `workflow_dispatch`. Runs `orchestrator remediate --issue <n>` |
| `.github/workflows/osv-status.yml` | `workflow_run` after scan/remediate. Runs `orchestrator status` and commits the result |
| `src/orchestrator/scan.py` | Runs osv-scanner, filters to PyPI, dedupes by `advisory_id`, opens Issues |
| `src/orchestrator/remediate.py` | Parses the OSV `Finding` from an Issue body, opens a Devin session, sends the activation message, polls until a PR appears, comments the PR URL on the Issue |
| `src/orchestrator/devin.py` | Devin v3 API client. Implements the Create + Message + Poll activation pattern |
| `src/orchestrator/prompts.py` | PyPI remediation prompt template |
| `src/orchestrator/github.py` | PyGithub wrapper. Issue title format, body template, label set, dedup query |
| `src/orchestrator/status.py` | Walks OSV issues, extracts linked PR / Devin session URLs from comments, renders `STATUS.md` |
| `STATUS.md` | Generated dashboard, viewed directly on GitHub |

## Setup

### Repository secrets

| Secret | How to obtain |
|---|---|
| `DEVIN_API_KEY` | Per the [Teams quickstart](https://docs.devin.ai/api-reference/getting-started/teams-quickstart): create a service user, then create an API key under that user. The key starts with `cog_` |
| `DEVIN_ORG_ID` | from the app.devin.ai workspace URL: the `org-...` segment |

Add both at **Settings → Secrets and variables → Actions**.

### Issue template

Manually-filed Issues use `.github/ISSUE_TEMPLATE/osv-finding-pypi.md`. `orchestrator scan` reproduces the same body structure programmatically; both routes converge on the same template so `remediate` can parse either.

## Operating

All three commands (`scan`, `remediate`, `status`) run automatically:

- `scan` — daily cron in `osv-scan.yml`
- `remediate` — `issues.opened` (filtered to `osv-finding`) in `osv-remediate.yml`
- `status` — `workflow_run` after either of the above completes, via `osv-status.yml`

For ad-hoc runs (re-scanning, replaying a remediation, regenerating the dashboard), each workflow exposes `workflow_dispatch` — use the **Run workflow** button on the Actions tab. `osv-remediate.yml` takes the issue number as an input.

A `Dockerfile` is provided for self-contained execution off-CI (debugging, alternative deployment targets); it bundles `osv-scanner` and exposes the same CLI.

## Live status

See [STATUS.md](./STATUS.md). Regenerated after every scan and remediate run by `osv-status.yml`.

## Design notes

- **1 Issue = 1 Devin session.** Cleaner failure isolation; `STATUS.md` maps session URL to advisory unambiguously. Trade-off: cannot batch multiple findings into a single PR.
- **PyPI only.** `scan.py` filters osv-scanner output by `ecosystem == "PyPI"` at parse time. Adding another ecosystem requires a new Issue template, a prompt template, and an `ecosystem`-branch in the orchestrator.
- **Create + Message activation.** The Devin v3 `prompt` field alone can leave a session in `status_detail: waiting_for_user`. `DevinClient.create_session` is therefore always followed by `send_message` with an explicit "begin" instruction.
- **Polling, not webhooks.** Devin v3 has no event push. `wait_for_completion` polls every 30s with a 30-minute timeout and returns early as soon as `pull_requests` is non-empty.
- **STATUS.md committed to the repo.** No separate dashboard service; the source of truth is git history.
