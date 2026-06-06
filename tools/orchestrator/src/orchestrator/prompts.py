"""Prompt templates for Devin sessions."""
from __future__ import annotations

from orchestrator.models import Finding


PYPI_REMEDIATION_TEMPLATE = """\
You are an autonomous security remediation agent. Work in the {owner}/{repo} GitHub repository.

Task: Remediate the vulnerability tracked at https://github.com/{owner}/{repo}/issues/{issue_number}.

The issue body contains an OSV finding ({package}, advisory {advisory_id}, current {current_version}, fixed {fixed_versions_str}) and a Remediation Steps section. Follow the issue body exactly.

This repo uses a two-layer Python dependency model:
- Do NOT manually edit requirements/*.txt (generated lockfiles).
- Update the source constraint in pyproject.toml (preferred) or requirements/*.in.
- Run ./scripts/uv-pip-compile.sh to regenerate lockfiles.
- Run pre-commit run --all-files before pushing.

Open a PR titled "fix(deps): bump {package} to address {preferred_alias}". PR body MUST contain "Closes #{issue_number}".

If you encounter ambiguity, choose the most conservative option and document the decision in the PR body. Do not stop to ask the user.
"""


NUDGE_MESSAGE = (
    "Begin the task as described in the initial prompt. "
    "Proceed autonomously without asking for clarification."
)


def build_pypi_remediation_prompt(
    *,
    owner: str,
    repo: str,
    issue_number: int,
    finding: Finding,
) -> str:
    return PYPI_REMEDIATION_TEMPLATE.format(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        package=finding.package,
        advisory_id=finding.advisory_id,
        current_version=finding.current_version,
        fixed_versions_str=", ".join(finding.fixed_versions),
        preferred_alias=finding.preferred_alias,
    )
