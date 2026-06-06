"""Run osv-scanner against Superset's pinned PyPI lockfiles and open Issues for new findings."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from orchestrator.models import Finding


PYPI_LOCKFILES = (
    "requirements/base.txt",
    "requirements/development.txt",
    "requirements/translations.txt",
)


def run(*, target: str, dry_run: bool) -> int:
    findings = _dedupe_by_advisory_id(scan_pypi(Path(target)))
    if not findings:
        print("scan: no PyPI vulnerabilities found")
        return 0

    print(f"scan: detected {len(findings)} PyPI vulnerabilit{'y' if len(findings) == 1 else 'ies'}")

    if dry_run:
        for finding in findings:
            print(json.dumps(asdict(finding), indent=2))
        return 0

    from orchestrator.github import GithubClient

    gh = GithubClient.from_env()
    existing = gh.existing_osv_advisory_ids()
    new_findings = [f for f in findings if f.advisory_id not in existing]
    print(f"scan: {len(new_findings)} new, {len(findings) - len(new_findings)} already filed")

    for finding in new_findings:
        issue = gh.create_finding_issue(finding)
        print(f"scan: created issue #{issue.number} for {finding.advisory_id} ({finding.package} {finding.current_version})")
        gh.dispatch_remediate(issue.number)
        print(f"scan: dispatched osv-remediate.yml for issue #{issue.number}")

    return 0


def scan_pypi(target_dir: Path) -> list[Finding]:
    target = target_dir.resolve()
    lockfiles = [lf for lf in PYPI_LOCKFILES if (target / lf).exists()]
    if not lockfiles:
        print(f"scan: no expected lockfiles under {target}", file=sys.stderr)
        return []

    args = ["osv-scanner", "--format=json", "--no-resolve"]
    for lockfile in lockfiles:
        args.append(f"--lockfile=requirements.txt:{lockfile}")

    result = subprocess.run(args, cwd=target, capture_output=True, text=True)
    # osv-scanner exits 0 when no vulns found, 1 when vulns found, >=2 on error
    if result.returncode > 1:
        raise RuntimeError(
            f"osv-scanner failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    if not result.stdout.strip():
        return []
    return parse_osv_json(result.stdout)


def parse_osv_json(json_str: str) -> list[Finding]:
    data = json.loads(json_str)
    findings: list[Finding] = []
    for result in data.get("results", []):
        source_path = result.get("source", {}).get("path", "")
        for pkg in result.get("packages", []):
            pkg_info = pkg.get("package", {})
            if pkg_info.get("ecosystem") != "PyPI":
                continue
            for vuln in pkg.get("vulnerabilities", []):
                findings.append(_build_finding(pkg_info, vuln, source_path))
    return findings


def _build_finding(pkg_info: dict, vuln: dict, source_path: str) -> Finding:
    return Finding(
        advisory_id=vuln["id"],
        aliases=list(vuln.get("aliases", [])),
        ecosystem=pkg_info.get("ecosystem", "PyPI"),
        package=pkg_info.get("name", ""),
        current_version=pkg_info.get("version", ""),
        fixed_versions=_extract_fixed_versions(vuln),
        source_manifest=source_path,
        severity=_extract_severity(vuln),
        summary=vuln.get("summary", ""),
    )


def _extract_fixed_versions(vuln: dict) -> list[str]:
    fixed: set[str] = set()
    for affected in vuln.get("affected", []):
        for range_ in affected.get("ranges", []):
            if range_.get("type") != "ECOSYSTEM":
                continue
            for event in range_.get("events", []):
                if "fixed" in event:
                    fixed.add(event["fixed"])
    return sorted(fixed)


def _dedupe_by_advisory_id(findings: list[Finding]) -> list[Finding]:
    """Keep one Finding per advisory_id; later duplicates are dropped."""
    seen: set[str] = set()
    deduped: list[Finding] = []
    for finding in findings:
        if finding.advisory_id in seen:
            continue
        seen.add(finding.advisory_id)
        deduped.append(finding)
    return deduped


def _extract_severity(vuln: dict) -> str | None:
    ds = vuln.get("database_specific") or {}
    if "severity" in ds:
        return ds["severity"]
    sev = vuln.get("severity") or []
    if sev:
        first = sev[0]
        return first.get("score") or first.get("type")
    return None
