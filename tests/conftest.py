"""Keep unit tests off the live web unless a test opts in."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _skip_live_model_research(monkeypatch):
    monkeypatch.setenv("RUN_FORREST_SKIP_MODEL_RESEARCH", "1")
    monkeypatch.setenv("RUN_FORREST_SKIP_SYNC", "1")
