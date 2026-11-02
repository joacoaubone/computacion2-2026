"""Fixtures compartidas de pytest para aislar las instantáneas del estado del TP2."""

import pytest


@pytest.fixture(autouse=True)
def use_temporary_snapshot_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("TP2_STATE_DIR", str(tmp_path / "snapshots"))
