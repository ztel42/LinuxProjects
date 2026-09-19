"""Collect systemd unit files and enabled/static unit listing."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..models import PersistenceEntry, SoftSkip

_EXEC_RE = re.compile(
    r"^(ExecStart(?:Pre|Post)?|ExecReload|ExecStop)\s*=\s*(.*)$",
    re.IGNORECASE,
)
_WANTED_BY_RE = re.compile(r"^WantedBy\s*=\s*(.*)$", re.IGNORECASE)
_UNIT_SUFFIXES = (".service", ".socket", ".path", ".timer", ".mount", ".target")


def _under_root(root: Optional[str], *parts: str) -> Path:
    if root:
        return Path(root).joinpath(*[p.lstrip("/") for p in parts])
    return Path("/").joinpath(*[p.lstrip("/") for p in parts])


def _read_text(path: Path, soft_skips: List[SoftSkip]) -> Optional[str]:
    try:
        if not path.exists() or not path.is_file():
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        soft_skips.append(SoftSkip(source=str(path), reason=f"unreadable: {exc}"))
        return None


def _parse_unit_file(path: Path, text: str) -> Dict[str, object]:
    execs: List[Dict[str, str]] = []
    wanted_by: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        m = _EXEC_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            # Strip systemd prefix flags like -, @, +
            cleaned = value.lstrip("-@:+!")
            # First token is typically the binary (may be quoted)
            binary = _first_exec_path(cleaned)
            execs.append({"key": key, "raw": value, "path": binary})
            continue
        m = _WANTED_BY_RE.match(line)
        if m:
            wanted_by.extend(t.strip() for t in m.group(1).split() if t.strip())
    return {"execs": execs, "wanted_by": wanted_by}


def _first_exec_path(value: str) -> str:
    """Extract the executable path from an Exec*= value."""
    value = value.strip()
    if not value:
        return ""
    if value.startswith('"'):
        end = value.find('"', 1)
        if end > 1:
            return value[1:end]
    # env VAR=... /path style — find first absolute or relative token that looks like a path
    tokens = value.split()
    for tok in tokens:
        if "=" in tok and not tok.startswith("/"):
            continue
        return tok
    return tokens[0] if tokens else ""


def _iter_unit_files(directory: Path, soft_skips: List[SoftSkip]) -> List[Path]:
    if not directory.exists():
        return []
    try:
        files: List[Path] = []
        for p in directory.rglob("*"):
            if p.is_file() and p.suffix in _UNIT_SUFFIXES:
                files.append(p)
        return sorted(files)
    except OSError as exc:
        soft_skips.append(SoftSkip(source=str(directory), reason=f"unreadable: {exc}"))
        return []


def _collect_unit_dirs(
    root: Optional[str], soft_skips: List[SoftSkip]
) -> List[PersistenceEntry]:
    entries: List[PersistenceEntry] = []
    dirs = [
        _under_root(root, "etc/systemd/system"),
        _under_root(root, "usr/lib/systemd/system"),
        _under_root(root, "lib/systemd/system"),
    ]

    # User systemd: live home or fixture homes
    if root:
        home_base = _under_root(root, "home")
        if home_base.is_dir():
            try:
                for user_home in home_base.iterdir():
                    user_units = user_home / ".config" / "systemd" / "user"
                    if user_units.is_dir():
                        dirs.append(user_units)
            except OSError as exc:
                soft_skips.append(
                    SoftSkip(source=str(home_base), reason=f"unreadable: {exc}")
                )
        # Also support root/.config/systemd/user in fixtures
        alt = _under_root(root, ".config/systemd/user")
        if alt.is_dir():
            dirs.append(alt)
    else:
        user_units = Path.home() / ".config" / "systemd" / "user"
        if user_units.is_dir():
            dirs.append(user_units)

    seen: set[str] = set()
    for d in dirs:
        for path in _iter_unit_files(d, soft_skips):
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            seen.add(key)
            text = _read_text(path, soft_skips)
            if text is None:
                continue
            parsed = _parse_unit_file(path, text)
            execs = parsed["execs"]  # type: ignore[assignment]
            wanted_by = parsed["wanted_by"]  # type: ignore[assignment]
            # One entry per unit file (aggregate ExecStart info)
            detail_parts = []
            for ex in execs:  # type: ignore[union-attr]
                detail_parts.append(f"{ex['key']}={ex['raw']}")
            detail = "; ".join(detail_parts) if detail_parts else path.name
            entries.append(
                PersistenceEntry(
                    category="systemd",
                    source=str(path),
                    detail=detail,
                    metadata={
                        "unit": path.name,
                        "execs": execs,
                        "wanted_by": wanted_by,
                        "unit_dir": str(d),
                    },
                )
            )
    return entries


def _collect_systemctl_list_unit_files(
    soft_skips: List[SoftSkip], *, skip: bool
) -> List[PersistenceEntry]:
    """Run systemctl list-unit-files when available (skipped under --root)."""
    entries: List[PersistenceEntry] = []
    if skip:
        soft_skips.append(
            SoftSkip(
                source="systemctl list-unit-files",
                reason="skipped under --root (offline fixture mode)",
            )
        )
        return entries

    if shutil.which("systemctl") is None:
        soft_skips.append(
            SoftSkip(source="systemctl list-unit-files", reason="systemctl not found")
        )
        return entries

    try:
        proc = subprocess.run(
            ["systemctl", "list-unit-files", "--no-pager", "--no-legend"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        soft_skips.append(
            SoftSkip(source="systemctl list-unit-files", reason=f"failed: {exc}")
        )
        return entries

    if proc.returncode != 0:
        soft_skips.append(
            SoftSkip(
                source="systemctl list-unit-files",
                reason=f"exit {proc.returncode}: {(proc.stderr or '').strip()[:200]}",
            )
        )
        return entries

    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        unit, state = parts[0], parts[1]
        # Focus on enabled/static (and generated/alias/enabled-runtime)
        if state.lower() not in {
            "enabled",
            "static",
            "enabled-runtime",
            "generated",
            "alias",
        }:
            continue
        entries.append(
            PersistenceEntry(
                category="systemd",
                source="systemctl list-unit-files",
                detail=f"{unit} {state}",
                metadata={"unit": unit, "state": state, "kind": "unit-file-state"},
            )
        )
    return entries


def collect_systemd(
    root: Optional[str] = None,
) -> Tuple[List[PersistenceEntry], List[SoftSkip]]:
    soft_skips: List[SoftSkip] = []
    entries = _collect_unit_dirs(root, soft_skips)
    entries.extend(
        _collect_systemctl_list_unit_files(soft_skips, skip=root is not None)
    )
    return entries, soft_skips
