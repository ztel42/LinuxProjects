"""Risk heuristics — flag suspicious persistence; never modify the host."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import List, Optional, Sequence

from .models import Finding, PersistenceEntry
from .pathsafe import lexically_inside, path_status, resolve_under_root

# Suspicious path prefixes / patterns for ExecStart binaries
_SUSPICIOUS_PREFIXES = ("/tmp/", "/dev/shm/")
_DOWNLOADS_RE = re.compile(r"^/home/[^/]+/Downloads/", re.IGNORECASE)

# Cron: curl/wget piped to bash/sh, or base64 pipes
_CRON_PIPE_RE = re.compile(
    r"(curl|wget).{0,80}\|\s*(/bin/)?(ba)?sh\b"
    r"|(base64).{0,40}\|\s*(/bin/)?(ba)?sh\b"
    r"|\|\s*base64\s+-d.{0,40}\|\s*(/bin/)?(ba)?sh\b",
    re.IGNORECASE,
)

_STANDARD_PREFIXES = (
    "/usr/",
    "/bin/",
    "/sbin/",
    "/lib/",
    "/lib64/",
    "/opt/",
    "/etc/",  # some ExecStart use /etc scripts — still "standard-ish"; exclude from non-standard
)


def _resolve_under_root(root: Optional[str], path: str) -> Optional[Path]:
    """Map an exec path under --root without following symlinks or ``..`` escapes.

    Returns None when the path would leave the root or any component is a symlink,
    so callers do not stat or read outside the fixture. Live scans (root is None)
    keep the host path.
    """
    if not path:
        return None
    if not root:
        return Path(path)
    resolved = resolve_under_root(root, path)
    if resolved is None:
        return None
    if not lexically_inside(Path(root), resolved):
        return None
    status = path_status(root, resolved)
    if status in {"symlink", "escape"}:
        return None
    return resolved


def _is_world_writable(path: Path, *, boundary: Optional[Path] = None) -> bool:
    """World-writable check. With ``boundary``, never stat above it or follow symlinks."""
    try:
        cur = path
        while True:
            if boundary is not None and not lexically_inside(boundary, cur):
                return False
            try:
                if cur.is_symlink():
                    return False
            except OSError:
                return False
            try:
                exists = cur.exists()
            except OSError:
                exists = False
            if exists:
                try:
                    mode = cur.lstat().st_mode if boundary is not None else cur.stat().st_mode
                except OSError:
                    return False
                if mode & stat.S_IWOTH:
                    return True
                if boundary is not None and os.path.abspath(cur) == os.path.abspath(boundary):
                    return False
            parent = cur.parent
            if parent == cur:
                return False
            cur = parent
    except OSError:
        return False


def _path_is_suspicious_location(exec_path: str) -> Optional[str]:
    if not exec_path:
        return None
    if any(exec_path.startswith(p) for p in _SUSPICIOUS_PREFIXES):
        return f"exec path under suspicious location: {exec_path}"
    if _DOWNLOADS_RE.match(exec_path):
        return f"exec path under user Downloads: {exec_path}"
    return None


def _is_nonstandard_path(exec_path: str) -> bool:
    if not exec_path or not exec_path.startswith("/"):
        return False
    return not any(exec_path.startswith(p) for p in _STANDARD_PREFIXES)


def analyze_entries(
    entries: Sequence[PersistenceEntry],
    *,
    root: Optional[str] = None,
) -> List[Finding]:
    """Apply heuristics to collected entries; return findings (no mutations)."""
    findings: List[Finding] = []

    for entry in entries:
        if entry.category == "cron":
            findings.extend(_analyze_cron(entry))
        elif entry.category == "systemd":
            findings.extend(_analyze_systemd(entry, root=root))
        # timers: informational inventory only unless detail embeds paths

    return findings


def _analyze_cron(entry: PersistenceEntry) -> List[Finding]:
    out: List[Finding] = []
    detail = entry.detail or ""
    if _CRON_PIPE_RE.search(detail):
        out.append(
            Finding(
                severity="high",
                rule="cron_pipe_download_exec",
                message="Cron line invokes curl/wget|bash or base64 pipe pattern",
                entry_category=entry.category,
                entry_source=entry.source,
                entry_detail=detail,
            )
        )
    # Also flag suspicious path references in cron command text
    for token in detail.split():
        tok = token.strip("'\"")
        msg = _path_is_suspicious_location(tok)
        if msg:
            out.append(
                Finding(
                    severity="high",
                    rule="cron_suspicious_path",
                    message=msg,
                    entry_category=entry.category,
                    entry_source=entry.source,
                    entry_detail=detail,
                )
            )
    return out


def _analyze_systemd(
    entry: PersistenceEntry, *, root: Optional[str]
) -> List[Finding]:
    out: List[Finding] = []
    meta = entry.metadata or {}
    if meta.get("kind") == "unit-file-state":
        return out  # listing-only rows

    execs = meta.get("execs") or []
    wanted_by = [w.lower() for w in (meta.get("wanted_by") or [])]
    multi_user = "multi-user.target" in wanted_by

    for ex in execs:
        exec_path = (ex.get("path") or "").strip()
        raw = ex.get("raw") or ""
        key = ex.get("key") or "ExecStart"

        msg = _path_is_suspicious_location(exec_path)
        if msg:
            out.append(
                Finding(
                    severity="high",
                    rule="systemd_suspicious_path",
                    message=f"{key}: {msg}",
                    entry_category=entry.category,
                    entry_source=entry.source,
                    entry_detail=entry.detail,
                )
            )

        resolved = _resolve_under_root(root, exec_path)
        # Escapes and symlinks yield None so we never stat outside --root.
        boundary = Path(root) if root else None
        if root:
            missing = (
                exec_path.startswith("/")
                and resolved is not None
                and path_status(root, resolved) == "missing"
            )
        else:
            missing = bool(exec_path.startswith("/") and resolved is not None and not resolved.exists())
        if missing:
            out.append(
                Finding(
                    severity="medium",
                    rule="systemd_missing_binary",
                    message=f"{key} binary missing: {exec_path}",
                    entry_category=entry.category,
                    entry_source=entry.source,
                    entry_detail=entry.detail,
                )
            )

        if exec_path.startswith("/") and resolved is not None and _is_world_writable(
            resolved, boundary=boundary
        ):
            out.append(
                Finding(
                    severity="high",
                    rule="systemd_world_writable",
                    message=f"{key} path is world-writable (or under world-writable dir): {exec_path}",
                    entry_category=entry.category,
                    entry_source=entry.source,
                    entry_detail=entry.detail,
                )
            )

        if multi_user and _is_nonstandard_path(exec_path):
            out.append(
                Finding(
                    severity="medium",
                    rule="systemd_nonstandard_enabled",
                    message=(
                        f"WantedBy=multi-user.target with non-standard path "
                        f"outside /usr,/bin,/sbin,/lib,/opt: {exec_path}"
                    ),
                    entry_category=entry.category,
                    entry_source=entry.source,
                    entry_detail=entry.detail,
                )
            )

        # Silence unused for linters
        _ = raw

    return out
