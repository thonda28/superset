"""CLI entry point for the orchestrator."""
from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orchestrator",
        description="Devin-powered OSV vulnerability remediation orchestrator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser(
        "scan",
        help="Run osv-scanner and create GitHub Issues for new findings",
    )
    scan.add_argument(
        "--target",
        default=".",
        help="Directory to scan (default: current directory)",
    )
    scan.add_argument(
        "--dry-run",
        action="store_true",
        help="Print findings without creating Issues",
    )

    remediate = sub.add_parser(
        "remediate",
        help="Start a Devin session for a specific Issue",
    )
    remediate.add_argument(
        "--issue",
        type=int,
        required=True,
        help="Issue number to remediate",
    )

    sub.add_parser("status", help="Regenerate STATUS.md")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "scan":
        from orchestrator.scan import run as scan_run

        return scan_run(target=args.target, dry_run=args.dry_run)
    if args.command == "remediate":
        from orchestrator.remediate import run as remediate_run

        return remediate_run(issue_number=args.issue)
    if args.command == "status":
        from orchestrator.status import run as status_run

        return status_run()
    return 1


if __name__ == "__main__":
    sys.exit(main())
