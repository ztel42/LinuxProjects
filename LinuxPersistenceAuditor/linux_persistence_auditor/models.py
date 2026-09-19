"""Shared data models for inventory findings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SoftSkip:
    """A path or command that could not be read/run (permission or missing)."""

    source: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class PersistenceEntry:
    """One inventoried persistence item (cron line, unit, timer, etc.)."""

    category: str  # cron | systemd | timer
    source: str  # file path or command
    detail: str  # line content, ExecStart, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    """A heuristic risk flag against an entry."""

    severity: str  # low | medium | high
    rule: str
    message: str
    entry_category: str
    entry_source: str
    entry_detail: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class AuditReport:
    """Full audit result."""

    entries: List[PersistenceEntry] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    soft_skips: List[SoftSkip] = field(default_factory=list)
    root: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "counts": {
                "entries": len(self.entries),
                "findings": len(self.findings),
                "soft_skips": len(self.soft_skips),
                "by_category": _count_by(self.entries, "category"),
                "findings_by_severity": _count_by(self.findings, "severity"),
            },
            "entries": [e.to_dict() for e in self.entries],
            "findings": [f.to_dict() for f in self.findings],
            "soft_skips": [s.to_dict() for s in self.soft_skips],
        }


def _count_by(items: List[Any], attr: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in items:
        key = getattr(item, attr)
        out[key] = out.get(key, 0) + 1
    return out
