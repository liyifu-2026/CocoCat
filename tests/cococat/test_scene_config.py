"""Tests for scene config."""
import os
import tempfile
import pytest
from cococat.scene.config import SceneConfig, load_scene_config, list_scenes


@pytest.fixture
def scenes_dir():
    with tempfile.TemporaryDirectory() as d:
        scene_dir = os.path.join(d, "customer-service")
        os.makedirs(scene_dir)

        scene_yaml = os.path.join(scene_dir, "scene.yaml")
        with open(scene_yaml, "w") as f:
            f.write("""id: customer-service
name: Customer Service
context: |
  You are a helpful customer service agent.
  Help users with refunds and order inquiries.
roster:
  - agent_a
  - agent_c
kbs:
  - product-manual
  - faq
skills:
  - crm-lookup
  - refund-procedure
channels:
  - type: wechat
    config:
      app_id: "wx123"
  - type: feishu
    config:
      app_id: "fei456"
""")
        yield d


def test_load_scene_config(scenes_dir):
    config = load_scene_config("customer-service", scenes_dir)
    assert config is not None
    assert config.id == "customer-service"
    assert config.name == "Customer Service"
    assert "helpful customer service" in config.context
    assert config.roster == ["agent_a", "agent_c"]
    assert config.kbs == ["product-manual", "faq"]
    assert config.skills == ["crm-lookup", "refund-procedure"]
    assert len(config.channels) == 2
    assert config.channels[0]["type"] == "wechat"
    assert config.channels[1]["type"] == "feishu"


def test_list_scenes(scenes_dir):
    scenes = list_scenes(scenes_dir)
    assert len(scenes) == 1
    assert scenes[0].id == "customer-service"


def test_load_nonexistent_scene(scenes_dir):
    config = load_scene_config("nonexistent", scenes_dir)
    assert config is None


def test_scene_config_default_values():
    d = {"id": "minimal", "name": "Minimal"}
    config = SceneConfig(**d)
    assert config.context == ""
    assert config.roster == []
    assert config.kbs == []
    assert config.skills == []
    assert config.channels == []
