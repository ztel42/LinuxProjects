"""Console, JSON, and CSV report writers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import TextIO

from .models import AuditReport

BANNER = """\
========================================================================
  AUTHORIZED HOSTS ONLY  |  READ-ONLY  |  NO CHANGES / NO DELETES
========================================================================
"""


def print_banner(stream: TextIO) -> None:
    stream.write(BANNER)
    stream.write("\n")


def print_summary(report: AuditReport, stream: TextIO) -> None:
    counts = report.to_dict()["counts"]
    stream.write("Linux Persistence Auditor — summary\n")
    if report.root:
        stream.write(f"  Fixture root : {report.root}\n")
    stream.write(f"  Entries      : {counts['entries']}\n")
    for cat, n in sorted(counts["by_category"].items()):
        stream.write(f"    - {cat}: {n}\n")
    stream.write(f"  Findings     : {counts['findings']}\n")
    for sev, n in sorted(counts["findings_by_severity"].items()):
        stream.write(f"    - {sev}: {n}\n")
    stream.write(f"  Soft-skips   : {counts['soft_skips']}\n")
    stream.write("\n")

    if report.soft_skips:
        stream.write("Soft-skips:\n")
        for s in report.soft_skips:
            stream.write(f"  • {s.source}: {s.reason}\n")
        stream.write("\n")

    if report.findings:
        stream.write("Findings:\n")
        for f in report.findings:
            stream.write(
                f"  [{f.severity.upper()}] {f.rule}: {f.message}\n"
                f"           source={f.entry_source}\n"
                f"           detail={f.entry_detail[:120]}\n"
            )
        stream.write("\n")
    else:
        stream.write("No heuristic findings.\n\n")


def write_json(report: AuditReport, path: str) -> None:
    Path(path).write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def write_csv(report: AuditReport, path: str) -> None:
    """Write findings (+ empty findings still create header). Soft-skips omitted."""
    fieldnames = [
        "severity",
        "rule",
        "message",
        "entry_category",
        "entry_source",
        "entry_detail",
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for f in report.findings:
            writer.writerow(f.to_dict())
