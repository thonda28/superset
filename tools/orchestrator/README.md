# Devin OSV Remediation Orchestrator

Event-driven security vulnerability remediation for Apache Superset, powered by [Devin](https://devin.ai).

## What it does

1. **Scan** (cron, daily) — runs `osv-scanner` against pinned Python dependencies and opens a GitHub Issue for each new finding, using the `osv-finding-pypi` issue template.
2. **Remediate** (on `issues.opened`) — hands the Issue to Devin via its API. Devin reads the issue body, updates the source constraint, regenerates lockfiles with `scripts/uv-pip-compile.sh`, runs `pre-commit`, and opens a PR satisfying the embedded Acceptance Criteria.
3. **Report** — regenerates [`STATUS.md`](./STATUS.md) with the current state of all findings, sessions, and PRs.

The orchestrator deliberately does only the deterministic work (scanning, Issue templating, GitHub I/O). The agentic work — reading repo conventions, choosing the right manifest, running multi-step shell commands, opening a properly-formatted PR — is delegated to Devin, where its judgment is the value-add.

## Live status

See [STATUS.md](./STATUS.md).

## Local invocation

```bash
cd tools/orchestrator
pip install -e .

# scan the parent superset checkout and open Issues for new findings
orchestrator scan --target ../..

# remediate a specific Issue
orchestrator remediate --issue 42

# regenerate STATUS.md
orchestrator status
```

## Docker

```bash
docker build -t devin-osv-orchestrator tools/orchestrator
docker run --rm \
  -e DEVIN_API_KEY="$DEVIN_API_KEY" \
  -e DEVIN_ORG_ID="$DEVIN_ORG_ID" \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e GITHUB_REPOSITORY=thonda28/superset \
  -v "$PWD:/workspace" \
  devin-osv-orchestrator scan --target /workspace
```

## Environment variables

| Name | Required | Description |
|---|---|---|
| `DEVIN_API_KEY` | yes | Devin v3 Service Account API key. Service Account keys only — Legacy/Personal keys return 401 on v3 endpoints. |
| `DEVIN_ORG_ID` | yes | Devin organization id (`org-...`). Get from the app.devin.ai workspace URL. |
| `GITHUB_TOKEN` | yes | GitHub token with `issues:write`, `contents:write`. In GitHub Actions, the default `GITHUB_TOKEN` is sufficient. |
| `GITHUB_REPOSITORY` | yes | Target repository in `owner/name` format. Auto-set in GitHub Actions. |
