"""Collect cron persistence from system and user crontab locations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from ..models import PersistenceEntry, SoftSkip


def _under_root(root: str | None, *parts: str) -> Path:
    if root:
        return Path(root).joinpath(*[p.lstrip("/") for p in parts])
    return Path("/").joinpath(*[p.lstrip("/") for p in parts])


def _read_text(path: Path, soft_skips: List[SoftSkip]) -> str | None:
    try:
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        soft_skips.append(SoftSkip(source=str(path), reason=f"unreadable: {exc}"))
        return None


def _is_cron_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    # Env assignments in crontab
    if "=" in stripped and not stripped[0].isdigit() and not stripped.startswith("@"):
        # SHELL=, PATH=, etc. — skip unless it looks like a schedule
        first = stripped.split(None, 1)[0]
        if first in {"SHELL", "PATH", "MAILTO", "HOME", "LOGNAME"} or (
            first.isupper() and "=" in first
        ):
            return False
        if stripped.split("=")[0].strip().isidentifier() and stripped.split("=")[0].isupper():
            return False
    return True


def _parse_crontab_lines(
    path: Path, text: str, entries: List[PersistenceEntry], *, kind: str
) -> None:
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not _is_cron_line(raw):
            continue
        entries.append(
            PersistenceEntry(
                category="cron",
                source=str(path),
                detail=raw.rstrip(),
                metadata={"kind": kind, "line": lineno},
            )
        )


def _iter_dir_files(directory: Path, soft_skips: List[SoftSkip]) -> List[Path]:
    if not directory.exists():
        return []
    try:
        return sorted(p for p in directory.iterdir() if p.is_file())
    except OSError as exc:
        soft_skips.append(SoftSkip(source=str(directory), reason=f"unreadable: {exc}"))
        return []


def collect_cron(root: str | None = None) -> Tuple[List[PersistenceEntry], List[SoftSkip]]:
    """Inventory cron jobs; soft-skip unreadable paths."""
    entries: List[PersistenceEntry] = []
    soft_skips: List[SoftSkip] = []

    # /etc/crontab
    etc_crontab = _under_root(root, "etc/crontab")
    text = _read_text(etc_crontab, soft_skips)
    if text is not None:
        _parse_crontab_lines(etc_crontab, text, entries, kind="etc_crontab")

    # /etc/cron.d/*
    for path in _iter_dir_files(_under_root(root, "etc/cron.d"), soft_skips):
        text = _read_text(path, soft_skips)
        if text is not None:
            _parse_crontab_lines(path, text, entries, kind="cron.d")

    # Periodic dirs: daily/hourly/weekly/monthly — list scripts as entries
    for period in ("daily", "hourly", "weekly", "monthly"):
        period_dir = _under_root(root, f"etc/cron.{period}")
        for path in _iter_dir_files(period_dir, soft_skips):
            # Skip .placeholder / disabled
            name = path.name
            if name.startswith(".") or name.endswith("~"):
                continue
            text = _read_text(path, soft_skips)
            detail = text.strip().splitlines()[0] if text and text.strip() else name
            # Prefer a short summary: first non-shebang/non-comment line if any
            body_preview = ""
            if text:
                for line in text.splitlines():
                    s = line.strip()
                    if s and not s.startswith("#") and not s.startswith("#!"):
                        body_preview = s
                        break
            entries.append(
                PersistenceEntry(
                    category="cron",
                    source=str(path),
                    detail=body_preview or detail,
                    metadata={"kind": f"cron.{period}", "script": name},
                )
            )

    # User crontabs
    for spool in ("var/spool/cron/crontabs", "var/spool/cron/crons"):
        spool_dir = _under_root(root, spool)
        for path in _iter_dir_files(spool_dir, soft_skips):
            text = _read_text(path, soft_skips)
            if text is not None:
                _parse_crontab_lines(path, text, entries, kind="user_crontab")

    return entries, soft_skips
