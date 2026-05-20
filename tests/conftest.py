"""Common test fixtures."""
import pytest
import tempfile
import os

from cococat.core.tools import resolve_tools_for_mode, ToolRegistry


@pytest.fixture
def registry():
    return ToolRegistry(resolve_tools_for_mode("default"))


@pytest.fixture
def tmp_file():
    """Create a temp file with known content. Returns (path, content)."""
    content = "hello world\nline 2\nline 3\n"
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt")
    tmp.write(content)
    tmp.close()
    yield tmp.name, content
    os.unlink(tmp.name)
