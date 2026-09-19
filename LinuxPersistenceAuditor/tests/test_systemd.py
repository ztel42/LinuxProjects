from __future__ import annotations

from linux_persistence_auditor.collectors.systemd import collect_systemd


def test_collect_systemd_units_from_fixture(fixture_root: str) -> None:
    entries, soft_skips = collect_systemd(fixture_root)
    # systemctl soft-skipped under --root
    assert any("list-unit-files" in s.source for s in soft_skips)

    unit_names = {
        (e.metadata or {}).get("unit")
        for e in entries
        if (e.metadata or {}).get("unit")
    }
    assert "evil-tmp.service" in unit_names
    assert "missing-bin.service" in unit_names
    assert "user-evil.service" in unit_names
    assert "ssh.service" in unit_names

    # ExecStart parsed
    evil = next(e for e in entries if e.metadata.get("unit") == "evil-tmp.service")
    paths = [ex["path"] for ex in evil.metadata["execs"]]
    assert "/tmp/evil.sh" in paths
