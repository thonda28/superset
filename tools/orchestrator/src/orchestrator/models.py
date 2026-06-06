"""Data models shared across orchestrator modules."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """A single OSV vulnerability finding.

    Mirrors the JSON block embedded in OSV Issue bodies and the output
    structure of osv-scanner (after filtering to ecosystem == "PyPI").
    """

    advisory_id: str
    aliases: list[str]
    ecosystem: str
    package: str
    current_version: str
    fixed_versions: list[str]
    source_manifest: str
    severity: str | None = None
    summary: str = ""
