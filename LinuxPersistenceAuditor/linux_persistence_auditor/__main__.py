"""Allow ``python -m linux_persistence_auditor``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
