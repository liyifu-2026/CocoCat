"""Tests for scene config in agent creation."""
import tempfile
import pytest
from cococat.core.agent import load_agent_config
from cococat.scene.config import SceneConfig


@pytest.fixture
def scene():
    return SceneConfig(
        id="test-scene",
        name="Test Scene",
        context="You help customers with refunds.",
        kbs=["product-manual", "faq"],
        skills=["refund_procedure", "crm_lookup"],
    )


def test_load_agent_config_with_scene_includes_context(scene):
    with tempfile.TemporaryDirectory() as d:
        config = load_agent_config(d, scene_config=scene)
        assert "refunds" in config.system_prompt.lower()
