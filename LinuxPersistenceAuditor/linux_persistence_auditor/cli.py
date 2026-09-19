"""CLI entry for Linux Persistence Auditor."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .collectors import collect_cron, collect_systemd, collect_timers
from .heuristics import analyze_entries
from .models import AuditReport, PersistenceEntry, SoftSkip
from .report import print_banner, print_summary, write_csv, write_json


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="linux_persistence_auditor",
        description=(
            "Read-only inventory of common Linux persistence mechanisms "
            "(cron, systemd, timers). Authorized hosts only."
        ),
    )
    p.add_argument(
        "--root",
        metavar="DIR",
        help="Point collectors at a fixture filesystem tree (offline / tests)",
    )
    p.add_argument(
        "--json",
        metavar="PATH",
        help="Write full JSON report to PATH",
    )
    p.add_argument(
        "--csv",
        metavar="PATH",
        help="Write findings CSV report to PATH",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return p


def run_audit(root: Optional[str] = None) -> AuditReport:
    entries: List[PersistenceEntry] = []
    soft_skips: List[SoftSkip] = []

    for collector in (collect_cron, collect_systemd, collect_timers):
        e, s = collector(root)
        entries.extend(e)
        soft_skips.extend(s)

    findings = analyze_entries(entries, root=root)
    return AuditReport(
        entries=entries,
        findings=findings,
        soft_skips=soft_skips,
        root=root,
    )


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    print_banner(sys.stdout)
    report = run_audit(root=args.root)
    print_summary(report, sys.stdout)

    if args.json:
        write_json(report, args.json)
        print(f"JSON report written: {args.json}")
    if args.csv:
        write_csv(report, args.csv)
        print(f"CSV report written: {args.csv}")

    return 0
