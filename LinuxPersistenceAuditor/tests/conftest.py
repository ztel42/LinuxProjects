from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "root"


@pytest.fixture
def fixture_root() -> str:
    return str(FIXTURE_ROOT.resolve())
