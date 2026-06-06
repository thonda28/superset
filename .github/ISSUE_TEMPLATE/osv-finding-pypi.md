---
name: OSV vulnerability finding (PyPI)
about: Python (PyPI) vulnerability detected by osv-scanner for Devin remediation
title: "[OSV][PyPI] "
labels: ["osv-finding", "auto-remediation", "security", "ecosystem:pypi"]
---

## OSV Finding

```json
{
  "advisory_id": "GHSA-xxxx-yyyy-zzzz",
  "aliases": ["CVE-2024-NNNNN"],
  "ecosystem": "PyPI",
  "package": "<package>",
  "current_version": "x.y.z",
  "fixed_versions": ["x.y.z+1"],
  "severity": "HIGH",
  "source_manifest": "requirements/base.txt",
  "summary": "<short description from advisory>"
}
```

## Remediation Steps (Superset-specific)

This repository uses a two-layer Python dependency model. **Do NOT edit
`requirements/*.txt` directly** — they are generated lockfiles.

1. Locate the source constraint for `<package>`:
   - If declared in `pyproject.toml` → update the version constraint there.
   - Otherwise → update the corresponding `requirements/*.in` file
     (e.g. `requirements/base.in`, `requirements/development.in`).
2. Run `./scripts/uv-pip-compile.sh` to regenerate `requirements/*.txt`.
3. Stage **both** the source constraint change and the regenerated
   `requirements/*.txt` files in a single commit.
4. Run `pre-commit run --all-files` and fix any issues before pushing.

## Acceptance Criteria

- [ ] `<package>` bumped to a version satisfying `fixed_versions`
- [ ] Both source constraint (`*.in` / `pyproject.toml`) and generated `*.txt` are updated together
- [ ] `pre-commit run --all-files` passes
- [ ] PR opened with title `fix(deps): bump <package> to address GHSA-xxxx`
- [ ] PR body contains `Closes #<this-issue-number>`

## Detection Context

- Scanner: `osv-scanner`
- Scope: pinned `requirements.txt`-style files only
  - `requirements/base.txt`
  - `requirements/development.txt`
  - `requirements/translations.txt`
- Command: `osv-scanner scan --lockfile=requirements.txt:<file> --no-resolve --format=json`
