"""Shared fixtures for db/ unit tests.

Sets dummy env vars BEFORE any db module is imported (config.py reads
os.environ at import time).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Must be set before db.config is imported anywhere.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")


@pytest.fixture
def mock_collection():
    """Patch _get_collection to return a MagicMock."""
    col = MagicMock()
    with patch("db.db._get_collection", return_value=col):
        yield col


@pytest.fixture
def mock_embed():
    """Patch embed_task to return a deterministic 1536-dim vector."""
    fake_embedding = [0.1] * 1536
    with patch("db.db.embed_task", return_value=fake_embedding) as m:
        yield m
