from __future__ import annotations

import pytest

from hands.bridge.brain_stub import ensure_brain_tables
from hands.db import connect, init_schema

from .. import outbox


@pytest.fixture
def conn(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "hub_test.db"))
    c = connect()
    ensure_brain_tables(c)
    init_schema(c)
    outbox.init_hub_schema(c)
    yield c
    c.close()
