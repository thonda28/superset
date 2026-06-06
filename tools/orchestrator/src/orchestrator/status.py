"""Render STATUS.md from the current state of OSV Issues and their PRs."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from orchestrator.models import Finding


_PR_URL_PATTERN = re.compile(r"https?://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)")
_SESSION_URL_PATTERN = re.compile(r"https?://app\.devin\.ai/sessions/[A-Za-z0-9_-]+")
_TITLE_PREFIX = "[OSV]"

_DEFAULT_OUTPUT = Path("tools") / "orchestrator" / "STATUS.md"


@dataclass
class IssueSnapshot:
    number: int
    title: str
    url: str
    state: str
    created_at: datetime
    closed_at: datetime | None
    finding: Finding | None
    pr_number: int | None
    pr_state: str | None
    pr_url: str | None
    session_url: str | None


def run(*, output: str | None = None) -> int:
    from orchestrator.github import GithubClient
    from orchestrator.remediate import parse_finding_from_issue_body

    gh = GithubClient.from_env()
    snapshots = list(_collect_snapshots(gh, parse_finding_from_issue_body))

    output_path = (Path(output) if output else Path.cwd() / _DEFAULT_OUTPUT).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render(snapshots), encoding="utf-8")
    print(f"status: wrote {output_path} ({len(snapshots)} OSV issue(s))")
    return 0


def _collect_snapshots(gh, parse_finding) -> Iterator[IssueSnapshot]:
    for issue in gh.repo.get_issues(state="all"):
        if issue.pull_request is not None:
            continue
        if not issue.title.startswith(_TITLE_PREFIX):
            continue
        yield _snapshot(issue, gh, parse_finding)


def _snapshot(issue, gh, parse_finding) -> IssueSnapshot:
    finding: Finding | None = None
    try:
        finding = parse_finding(issue.body or "")
    except (ValueError, KeyError):
        pass

    pr_number: int | None = None
    pr_url: str | None = None
    session_url: str | None = None
    for comment in issue.get_comments():
        body = comment.body or ""
        if pr_number is None:
            m = _PR_URL_PATTERN.search(body)
            if m:
                pr_number = int(m.group(1))
                pr_url = m.group(0)
        if session_url is None:
            m = _SESSION_URL_PATTERN.search(body)
            if m:
                session_url = m.group(0)

    pr_state: str | None = None
    if pr_number is not None:
        try:
            pr = gh.repo.get_pull(pr_number)
            pr_state = "merged" if pr.merged else pr.state
        except Exception:
            pr_state = "unknown"

    return IssueSnapshot(
        number=issue.number,
        title=issue.title,
        url=issue.html_url,
        state=issue.state,
        created_at=issue.created_at,
        closed_at=issue.closed_at,
        finding=finding,
        pr_number=pr_number,
        pr_state=pr_state,
        pr_url=pr_url,
        session_url=session_url,
    )


def render(snapshots: list[IssueSnapshot]) -> str:
    open_issues = sorted(
        (s for s in snapshots if s.state == "open"),
        key=lambda s: s.number,
        reverse=True,
    )
    closed_issues = sorted(
        (s for s in snapshots if s.state == "closed"),
        key=lambda s: s.closed_at or s.created_at,
        reverse=True,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# OSV Remediation Status",
        "",
        f"_Generated at {now}_",
        "",
        "## Summary",
        "",
        f"- Open findings: **{len(open_issues)}**",
        f"- Remediated (closed): **{len(closed_issues)}**",
        "",
    ]

    if open_issues:
        lines += [
            "## Open Findings",
            "",
            "| Issue | Package | Advisory | Source manifest | Devin session | PR |",
            "|---|---|---|---|---|---|",
        ]
        for s in open_issues:
            lines.append(_open_row(s))
        lines.append("")

    if closed_issues:
        lines += [
            "## Remediated",
            "",
            "| Issue | Package | Advisory | PR | Closed |",
            "|---|---|---|---|---|",
        ]
        for s in closed_issues:
            lines.append(_closed_row(s))
        lines.append("")

    if not open_issues and not closed_issues:
        lines += ["_No OSV findings recorded yet._", ""]

    return "\n".join(lines)


def _open_row(s: IssueSnapshot) -> str:
    pkg = f"`{s.finding.package} {s.finding.current_version}`" if s.finding else "?"
    advisory = s.finding.preferred_alias if s.finding else "?"
    source = f"`{s.finding.source_manifest}`" if s.finding and s.finding.source_manifest else "—"
    session = f"[link]({s.session_url})" if s.session_url else "—"
    pr = f"[#{s.pr_number}]({s.pr_url}) ({s.pr_state})" if s.pr_number else "—"
    return f"| [#{s.number}]({s.url}) | {pkg} | {advisory} | {source} | {session} | {pr} |"


def _closed_row(s: IssueSnapshot) -> str:
    pkg = f"`{s.finding.package} {s.finding.current_version}`" if s.finding else "?"
    advisory = s.finding.preferred_alias if s.finding else "?"
    pr = f"[#{s.pr_number}]({s.pr_url}) ({s.pr_state})" if s.pr_number else "—"
    closed_at = s.closed_at.strftime("%Y-%m-%d") if s.closed_at else "?"
    return f"| [#{s.number}]({s.url}) | {pkg} | {advisory} | {pr} | {closed_at} |"
