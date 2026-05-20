import pytest
from cococat.core.modes import load_mode, list_modes


def test_load_default_mode():
    mode = load_mode("default")
    assert mode.id == "default"
    assert mode.name == "Coco"
    assert "sub_agent" in mode.tools
    assert "你是 Coco" in mode.system_prompt


def test_load_kb_admin_mode():
    mode = load_mode("kb-admin")
    assert mode.id == "kb-admin"
    assert "write_file" in mode.tools
    assert "bash" in mode.tools


def test_list_modes():
    modes = list_modes()
    assert len(modes) >= 2
    ids = [m.id for m in modes]
    assert "default" in ids
    assert "kb-admin" in ids


def test_load_nonexistent_mode():
    with pytest.raises(FileNotFoundError):
        load_mode("nonexistent")


def test_mode_config_immutability():
    mode = load_mode("default")
    with pytest.raises(Exception):
        mode.tools = ("extra",)
