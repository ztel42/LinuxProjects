from __future__ import annotations

from linux_persistence_auditor.collectors.timers import collect_timers


def test_timers_soft_skip_under_root(fixture_root: str) -> None:
    entries, soft_skips = collect_timers(fixture_root)
    assert entries == []
    assert any("list-timers" in s.source for s in soft_skips)
