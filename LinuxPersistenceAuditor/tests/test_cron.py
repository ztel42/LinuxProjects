from __future__ import annotations

from linux_persistence_auditor.collectors.cron import collect_cron


def test_collect_cron_from_fixture(fixture_root: str) -> None:
    entries, soft_skips = collect_cron(fixture_root)
    assert soft_skips == [] or all(isinstance(s.reason, str) for s in soft_skips)
    sources = {e.source for e in entries}
    assert any(s.endswith("etc/crontab") for s in sources)
    assert any("cron.d/suspicious" in s for s in sources)
    assert any("crontabs/alice" in s for s in sources)
    assert any("cron.hourly/decode" in s for s in sources)
    # At least one curl|bash style line
    details = "\n".join(e.detail for e in entries)
    assert "curl" in details.lower() or "wget" in details.lower()
