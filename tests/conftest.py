"""Pytest configuration."""

import pytest
import os
import tempfile


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_sessions():
    """Create a temporary sessions directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir
