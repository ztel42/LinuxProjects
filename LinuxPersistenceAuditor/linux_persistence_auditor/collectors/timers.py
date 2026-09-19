"""Collect systemd timers via systemctl list-timers."""

from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional, Tuple

from ..models import PersistenceEntry, SoftSkip


def collect_timers(
    root: Optional[str] = None,
) -> Tuple[List[PersistenceEntry], List[SoftSkip]]:
    """Inventory timers; soft-skip when systemctl unavailable or under --root."""
    entries: List[PersistenceEntry] = []
    soft_skips: List[SoftSkip] = []

    if root is not None:
        soft_skips.append(
            SoftSkip(
                source="systemctl list-timers --all",
                reason="skipped under --root (offline fixture mode)",
            )
        )
        # Still note timer unit files discovered under root via systemd collector.
        return entries, soft_skips

    if shutil.which("systemctl") is None:
        soft_skips.append(
            SoftSkip(source="systemctl list-timers --all", reason="systemctl not found")
        )
        return entries, soft_skips

    try:
        proc = subprocess.run(
            ["systemctl", "list-timers", "--all", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        soft_skips.append(
            SoftSkip(source="systemctl list-timers --all", reason=f"failed: {exc}")
        )
        return entries, soft_skips

    if proc.returncode != 0:
        soft_skips.append(
            SoftSkip(
                source="systemctl list-timers --all",
                reason=f"exit {proc.returncode}: {(proc.stderr or '').strip()[:200]}",
            )
        )
        return entries, soft_skips

    lines = proc.stdout.splitlines()
    # Skip header until we see a blank or "NEXT" header processed
    data_started = False
    for line in lines:
        if not line.strip():
            if data_started:
                break
            continue
        if line.startswith("NEXT") or line.startswith("PASS"):
            data_started = True
            continue
        if not data_started:
            # Some versions print without needing flag — try parse anyway
            data_started = True
        # Columns vary; last tokens often include UNIT and ACTIVATES
        parts = line.split()
        if len(parts) < 2:
            continue
        # Heuristic: find *.timer token
        timer_unit = next((p for p in parts if p.endswith(".timer")), None)
        if not timer_unit:
            continue
        entries.append(
            PersistenceEntry(
                category="timer",
                source="systemctl list-timers --all",
                detail=line.strip(),
                metadata={"unit": timer_unit},
            )
        )

    return entries, soft_skips
