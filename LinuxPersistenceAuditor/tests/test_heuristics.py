from __future__ import annotations

from linux_persistence_auditor.collectors import collect_cron, collect_systemd
from linux_persistence_auditor.heuristics import analyze_entries


def test_heuristics_flag_fixture_risks(fixture_root: str) -> None:
    entries = []
    for coll in (collect_cron, collect_systemd):
        e, _ = coll(fixture_root)
        entries.extend(e)

    findings = analyze_entries(entries, root=fixture_root)
    rules = {f.rule for f in findings}

    assert "cron_pipe_download_exec" in rules
    assert "systemd_suspicious_path" in rules
    assert "systemd_missing_binary" in rules
    assert "systemd_nonstandard_enabled" in rules

    # Downloads / tmp / shm covered
    messages = " ".join(f.message for f in findings)
    assert "/tmp/" in messages or "Downloads" in messages
