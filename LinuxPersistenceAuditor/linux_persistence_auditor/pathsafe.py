"""Contain filesystem access under an optional --root.

Candidate paths are joined lexically under the root. ``..`` components and
absolute paths that would leave the root are rejected. Symlinks are never
followed: directory walks skip them and reads use ``O_NOFOLLOW``. Real files
that stay inside the root are still readable.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Optional


def lexically_inside(base: Path, path: Path) -> bool:
    """True when ``path`` stays inside ``base`` after lexical ``..`` normalization.

    Does not resolve symlinks (``os.path.abspath`` only).
    """
    base_s = os.path.abspath(os.fspath(base))
    path_s = os.path.abspath(os.fspath(path))
    if path_s == base_s:
        return True
    return path_s.startswith(base_s.rstrip("/") + "/")


def resolve_under_root(root: Optional[str], *parts: str) -> Optional[Path]:
    """Lexically join *parts* under ``root`` (or ``/`` when root is None).

    When a fixture root is set, absolute parts are re-rooted under it.
    Returns None if a ``..`` component would escape that base.
    Does not touch the filesystem and does not resolve symlinks.
    """
    base = Path(root) if root else Path("/")
    segments: list[str] = []

    for part in parts:
        text = str(part).replace("\\", "/")
        if not text:
            continue
        if text.startswith("/"):
            # Restart at the base. Fixture mode re-roots absolute paths;
            # live mode (root is None) restarts at filesystem root.
            segments = []
            text = text.lstrip("/")
        for comp in PurePosixPath(text).parts:
            if comp in ("", ".", "/"):
                continue
            if comp == "..":
                if not segments:
                    return None
                segments.pop()
                continue
            if "\x00" in comp:
                return None
            segments.append(comp)

    candidate = base.joinpath(*segments) if segments else base
    if root is not None and not lexically_inside(base, candidate):
        return None
    if root is None and not lexically_inside(Path("/"), candidate):
        return None
    return candidate


def path_status(root: Optional[str], path: Path) -> str:
    """Classify ``path`` without following symlinks.

    Returns one of: ``file``, ``dir``, ``missing``, ``symlink``, ``escape``.
    """
    if root is not None:
        base = Path(root)
        if not lexically_inside(base, path):
            return "escape"
        base_abs = Path(os.path.abspath(base))
        target = Path(os.path.abspath(path))
        try:
            rel_parts = target.relative_to(base_abs, walk_up=False).parts
        except ValueError:
            return "escape"
        if any(part == ".." for part in rel_parts):
            return "escape"
        current = base_abs
        if not rel_parts:
            return _leaf_status(current, allow_root_symlink=True)
        for index, part in enumerate(rel_parts):
            current = current / part
            try:
                if current.is_symlink():
                    return "symlink"
            except OSError:
                return "escape"
            last = index == len(rel_parts) - 1
            if not last:
                try:
                    if not current.is_dir():
                        return "missing"
                except OSError:
                    return "escape"
                continue
            return _leaf_status(current, allow_root_symlink=False)
    return _leaf_status(path, allow_root_symlink=False)


def _leaf_status(path: Path, *, allow_root_symlink: bool) -> str:
    try:
        if path.is_symlink():
            if allow_root_symlink and path.is_dir():
                return "dir"
            return "symlink"
        if path.is_file():
            return "file"
        if path.is_dir():
            return "dir"
    except OSError:
        return "escape"
    return "missing"


def is_real_dir(root: Optional[str], path: Path) -> bool:
    return path_status(root, path) == "dir"


def read_text_nofollow(path: Path) -> str:
    """Read a regular file. The final path component is not followed if it is a symlink."""
    flags = os.O_RDONLY | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(os.fspath(path), flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise OSError(f"not a regular file: {path}")
        chunks: list[bytes] = []
        while True:
            data = os.read(fd, 65536)
            if not data:
                break
            chunks.append(data)
    finally:
        os.close(fd)
    return b"".join(chunks).decode("utf-8", errors="replace")


def iter_real_files(root: Optional[str], directory: Path) -> List[Path]:
    """List regular files in ``directory``, skipping symlink entries. Not recursive."""
    if path_status(root, directory) != "dir":
        return []
    found: List[Path] = []
    with os.scandir(directory) as scan:
        for entry in scan:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    found.append(Path(directory) / entry.name)
            except OSError:
                continue
    return sorted(found, key=lambda p: p.name)


def iter_real_files_recursive(
    root: Optional[str], directory: Path, suffixes: Iterable[str]
) -> List[Path]:
    """Walk ``directory`` without following symlinks. Keep files whose suffix matches."""
    if path_status(root, directory) != "dir":
        return []
    suffix_set = tuple(suffixes)
    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        base = Path(dirpath)
        if root is not None and path_status(root, base) != "dir":
            dirnames[:] = []
            continue
        kept: list[str] = []
        for name in dirnames:
            child = base / name
            try:
                if child.is_symlink():
                    continue
            except OSError:
                continue
            if root is not None and path_status(root, child) != "dir":
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            child = base / name
            try:
                if child.is_symlink():
                    continue
                if suffix_set and child.suffix not in suffix_set:
                    continue
                if child.is_file() and not child.is_symlink():
                    found.append(child)
            except OSError:
                continue
    return sorted(found)
