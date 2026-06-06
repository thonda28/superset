"""Thin PyGithub wrapper for orchestrator operations on the target repo."""
from __future__ import annotations

import json
import os
import re
from typing import Iterable

from github import Github
from github.Issue import Issue
from github.Repository import Repository

from orchestrator.models import Finding


OSV_LABELS = ["osv-finding", "auto-remediation", "security", "ecosystem:pypi"]

_TITLE_PREFIX = "[OSV][PyPI]"
_ADVISORY_ID_PATTERN = re.compile(r'"advisory_id"\s*:\s*"([^"]+)"')


class GithubClient:
    def __init__(self, token: str, repo_full_name: str) -> None:
        self._gh = Github(token)
        self.repo: Repository = self._gh.get_repo(repo_full_name)

    @classmethod
    def from_env(cls) -> "GithubClient":
        token = os.environ["GITHUB_TOKEN"]
        repo = os.environ["GITHUB_REPOSITORY"]
        return cls(token, repo)

    def existing_osv_advisory_ids(self) -> set[str]:
        """Advisory IDs already filed as open OSV Issues.

        Dedup key is the ``advisory_id`` JSON field inside each Issue body.
        Title prefix filtering keeps the loop cheap on repos with many Issues.
        """
        ids: set[str] = set()
        for issue in self.repo.get_issues(state="open"):
            if not issue.title.startswith(_TITLE_PREFIX):
                continue
            advisory_id = _extract_advisory_id(issue.body or "")
            if advisory_id:
                ids.add(advisory_id)
        return ids

    def create_finding_issue(self, finding: Finding) -> Issue:
        title = _build_title(finding)
        body = _build_body(finding)
        return self.repo.create_issue(title=title, body=body, labels=OSV_LABELS)


def _build_title(finding: Finding) -> str:
    return f"{_TITLE_PREFIX} {finding.package} {finding.current_version} vulnerable to {finding.preferred_alias}"


def _build_body(finding: Finding) -> str:
    finding_json = json.dumps(
        {
            "advisory_id": finding.advisory_id,
            "aliases": finding.aliases,
            "ecosystem": finding.ecosystem,
            "package": finding.package,
            "current_version": finding.current_version,
            "fixed_versions": finding.fixed_versions,
            "severity": finding.severity,
            "source_manifest": finding.source_manifest,
            "summary": finding.summary,
        },
        indent=2,
    )
    return _ISSUE_BODY_TEMPLATE.format(
        finding_json=finding_json,
        package=finding.package,
        preferred_alias=finding.preferred_alias,
        source_manifest=finding.source_manifest,
    )


def _extract_advisory_id(body: str) -> str | None:
    match = _ADVISORY_ID_PATTERN.search(body)
    return match.group(1) if match else None


_ISSUE_BODY_TEMPLATE = """\
## OSV Finding

```json
{finding_json}
```

## Remediation Steps (Superset-specific)

This repository uses a two-layer Python dependency model. **Do NOT edit
`requirements/*.txt` directly** — they are generated lockfiles.

1. Locate the source constraint for `{package}`:
    - If declared in `pyproject.toml` → update the version constraint there.
    - Otherwise → update the corresponding `requirements/*.in` file
      (e.g. `requirements/base.in`, `requirements/development.in`).
2. Run `./scripts/uv-pip-compile.sh` to regenerate `requirements/*.txt`.
3. Stage **both** the source constraint change and the regenerated
    `requirements/*.txt` files in a single commit.
4. Run `pre-commit run --all-files` and fix any issues before pushing.

## Acceptance Criteria

- [ ] `{package}` bumped to a version satisfying `fixed_versions`
- [ ] Both source constraint (`*.in` / `pyproject.toml`) and generated `*.txt` are updated together
- [ ] `pre-commit run --all-files` passes
- [ ] PR opened with title `fix(deps): bump {package} to address {preferred_alias}`
- [ ] PR body contains `Closes #<this-issue-number>`

## Detection Context

- Scanner: `osv-scanner`
- Source manifest: `{source_manifest}`
- Command: `osv-scanner --lockfile=requirements.txt:{source_manifest} --no-resolve --format=json`
"""
