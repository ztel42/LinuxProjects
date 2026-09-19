# LinuxPersistenceAuditor

Read-only **Linux persistence inventory CLI** for Pop!_OS / Ubuntu / systemd hosts.

It scans common persistence mechanisms (cron, systemd units, timers), applies lightweight risk heuristics, and prints a console summary with optional JSON/CSV reports. A **`--root DIR`** mode points collectors at a fixture filesystem tree so tests and offline demos work without root or a live systemd.

```
========================================================================
  AUTHORIZED HOSTS ONLY  |  READ-ONLY  |  NO CHANGES / NO DELETES
========================================================================
```

**Author:** Zach Telford ([ztel42](https://github.com/ztel42))

---

## Disclaimer

- Use only on **hosts you own or are explicitly authorized** to assess.
- This tool is **read-only by design**. It does **not** disable, delete, or modify persistence entries.
- Findings are heuristic review signals, not a full incident-response or malware analysis.
- Some paths (e.g. other users’ crontabs) may be unreadable without elevated privileges; those are **soft-skipped** with a note.

---

## Features

| Area | What it collects |
| --- | --- |
| **Cron** | `/etc/crontab`, `/etc/cron.d/*`, `/etc/cron.{daily,hourly,weekly,monthly}/*`, user crontabs under `/var/spool/cron/crontabs/*` (and `/var/spool/cron/crons/*` if present) |
| **Systemd** | Enabled/static units via `systemctl list-unit-files` (when available); unit files under `/etc/systemd/system`, `/usr/lib/systemd/system`, `/lib/systemd/system`; user units under `~/.config/systemd/user` |
| **Timers** | `systemctl list-timers --all` when available |

### Risk heuristics (flag only)

- Exec paths under `/tmp`, `/dev/shm`, `/home/*/Downloads`, or world-writable directories
- Missing `ExecStart` / `ExecStartPre` binaries (broken units)
- Cron lines matching simple `curl|wget|bash` or `base64` pipe patterns
- Units with `WantedBy=multi-user.target` pointing at non-standard paths outside `/usr`, `/bin`, `/sbin`, `/lib`, `/opt`

---

## Soft-skip behavior

Unreadable files/directories and unavailable `systemctl` commands are recorded as **soft-skips** (path + reason) instead of aborting the run. Under `--root`, live `systemctl` queries are skipped by design.

---

## Requirements

- Python 3.10+ (stdlib only for the auditor; `pytest` for tests)
- Target: systemd-based Linux (Pop!_OS / Ubuntu). Offline `--root` works on any OS with the fixture tree.

---

## Usage

```bash
# From the project directory
python -m linux_persistence_auditor

# JSON + CSV reports
python -m linux_persistence_auditor --json report.json --csv findings.csv

# Offline / fixture mode (no root, no systemd required)
python -m linux_persistence_auditor --root tests/fixtures/root --json out.json
```

---

## Examples

Console summary includes entry counts by category, findings by severity, and soft-skip notes:

```text
Linux Persistence Auditor — summary
  Fixture root : .../tests/fixtures/root
  Entries      : 20
    - cron: 8
    - systemd: 12
  Findings     : 10
    - high: 7
    - medium: 3
  Soft-skips   : 2
```

---

## Tests

```bash
pip install -r requirements.txt
python -m pytest
```

Tests use `--root` against `tests/fixtures/root` and do **not** require systemd privileges.

---

## Layout

```text
LinuxPersistenceAuditor/
├── linux_persistence_auditor/
│   ├── collectors/     # cron, systemd, timers
│   ├── heuristics.py
│   ├── report.py
│   ├── cli.py
│   └── __main__.py
├── tests/
│   └── fixtures/root/  # offline filesystem tree
├── requirements.txt
└── README.md
```
