import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from scene_package import export_scene, import_scene
import json


def test_export_scene():
    result = export_scene("customer-service")
    assert "exported" in result
    import glob
    for f in glob.glob(os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes", "customer-service-*.zip")):
        os.remove(f)


def test_import_scene():
    export_scene("customer-service")
    import glob
    scenes_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes")
    zips = glob.glob(os.path.join(scenes_dir, "customer-service-*.zip"))
    if zips:
        result = import_scene(zips[0])
        assert "imported" in result
        os.remove(zips[0])


def test_scene_has_required_files():
    scene_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes", "customer-service")
    assert os.path.exists(os.path.join(scene_dir, "scene.json"))
    assert os.path.exists(os.path.join(scene_dir, "CONTEXT.md"))
    assert os.path.exists(os.path.join(scene_dir, "config.json"))
    assert os.path.exists(os.path.join(scene_dir, "skills", "manifest.json"))


def test_config_has_pending_status():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes", "customer-service", "config.json")
    with open(config_path) as f:
        config = json.load(f)
    assert config.get("status") == "pending_config"


def test_scene_json_has_entries():
    scene_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenes", "customer-service", "scene.json")
    with open(scene_path) as f:
        scene = json.load(f)
    assert len(scene.get("entries", [])) > 0
    assert scene["entries"][0]["channel"] == "web_api"
