import os, shutil
import pytest
from cococat.core.tools.kb_tools import _create_kb


def test_create_kb():
    name = "test-create-kb"
    path = os.path.join("knowledge", name)
    if os.path.exists(path):
        shutil.rmtree(path)
    try:
        result = _create_kb({"kb_name": name, "purpose": "Test KB"}, None)
        assert "Created" in result
        assert os.path.exists(os.path.join(path, "wiki", "entities"))
        assert os.path.exists(os.path.join(path, "wiki", "concepts"))
        assert os.path.exists(os.path.join(path, "raw", "sources"))
        assert os.path.exists(os.path.join(path, "purpose.md"))
        assert os.path.exists(os.path.join(path, "index.md"))
        assert os.path.exists(os.path.join(path, "log.md"))
    finally:
        shutil.rmtree(path)


def test_create_kb_already_exists():
    name = "test-create-kb-exists"
    path = os.path.join("knowledge", name)
    os.makedirs(os.path.join(path, "wiki"), exist_ok=True)
    try:
        result = _create_kb({"kb_name": name}, None)
        assert "already exists" in result
    finally:
        shutil.rmtree(path)


def test_create_kb_missing_name():
    result = _create_kb({}, None)
    assert "Error" in result
