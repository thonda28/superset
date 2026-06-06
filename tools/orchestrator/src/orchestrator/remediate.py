"""Issue -> Devin session orchestration."""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from orchestrator.models import Finding


_JSON_BLOCK_PATTERN = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def run(*, issue_number: int) -> int:
    from orchestrator.devin import DevinClient
    from orchestrator.github import GithubClient
    from orchestrator.prompts import NUDGE_MESSAGE, build_pypi_remediation_prompt

    repo_full = os.environ["GITHUB_REPOSITORY"]
    owner, repo_name = repo_full.split("/", 1)

    gh = GithubClient.from_env()
    issue = gh.repo.get_issue(issue_number)
    try:
        finding = parse_finding_from_issue_body(issue.body or "")
    except ValueError as exc:
        print(f"remediate: cannot parse OSV finding from issue #{issue_number}: {exc}", file=sys.stderr)
        return 3

    if finding.ecosystem != "PyPI":
        print(
            f"remediate: ecosystem={finding.ecosystem!r} is not supported (PyPI only)",
            file=sys.stderr,
        )
        return 3

    print(
        f"remediate: starting Devin session for issue #{issue_number} "
        f"({finding.package} {finding.advisory_id})"
    )

    devin = DevinClient.from_env()
    prompt = build_pypi_remediation_prompt(
        owner=owner,
        repo=repo_name,
        issue_number=issue_number,
        finding=finding,
    )
    session = devin.create_session(
        prompt=prompt,
        tags=[
            "osv-finding",
            "auto-remediation",
            f"issue:{issue_number}",
            finding.advisory_id,
        ],
    )
    print(f"remediate: created session {session.session_id} -> {session.url}")

    devin.send_message(session.session_id, NUDGE_MESSAGE)
    print("remediate: nudge sent; polling for completion")

    final = devin.wait_for_completion(session.session_id)
    print(
        f"remediate: terminal status={final.status}/{final.status_detail} "
        f"acus_consumed={final.acus_consumed}"
    )

    if final.pull_requests:
        pr = final.pull_requests[0]
        pr_url = pr.get("pr_url") or pr.get("url") or "(no url)"
        issue.create_comment(
            f"Devin opened a remediation PR: {pr_url}\n\nSession: {final.url}"
        )
        print(f"remediate: PR opened: {pr_url}")
        gh.dispatch_status()
        print("remediate: dispatched osv-status.yml")
        return 0

    issue.create_comment(
        f"Devin session ended without opening a PR. "
        f"Session: {final.url} (status: {final.status})"
    )
    print("remediate: no PR produced", file=sys.stderr)
    gh.dispatch_status()
    print("remediate: dispatched osv-status.yml")
    return 4


def parse_finding_from_issue_body(body: str) -> Finding:
    """Extract the OSV ``Finding`` from the JSON code block in an issue body."""
    match = _JSON_BLOCK_PATTERN.search(body)
    if not match:
        raise ValueError("issue body does not contain a ```json``` code block")
    data: dict[str, Any] = json.loads(match.group(1))
    return Finding(
        advisory_id=data["advisory_id"],
        aliases=list(data.get("aliases") or []),
        ecosystem=data.get("ecosystem") or "PyPI",
        package=data["package"],
        current_version=data["current_version"],
        fixed_versions=list(data.get("fixed_versions") or []),
        source_manifest=data.get("source_manifest") or "",
        severity=data.get("severity"),
        summary=data.get("summary") or "",
    )
