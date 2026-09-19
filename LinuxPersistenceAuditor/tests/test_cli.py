from __future__ import annotations

import json
from pathlib import Path

from linux_persistence_auditor.cli import main, run_audit


def test_run_audit_fixture(fixture_root: str) -> None:
    report = run_audit(root=fixture_root)
    assert report.root == fixture_root
    assert len(report.entries) > 0
    assert len(report.findings) > 0


def test_cli_json_csv(fixture_root: str, tmp_path: Path, capsys) -> None:
    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"
    rc = main(
        [
            "--root",
            fixture_root,
            "--json",
            str(json_path),
            "--csv",
            str(csv_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "AUTHORIZED HOSTS ONLY" in out
    assert "READ-ONLY" in out
    assert json_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["counts"]["entries"] >= 1
    assert data["counts"]["findings"] >= 1
    assert csv_path.is_file()
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "severity" in csv_text.splitlines()[0]
