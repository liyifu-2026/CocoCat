"""Plugin manager — discover, load, install, and manage plugins."""
import os
import sys
import json
import shutil
import tempfile
import importlib.util
from pathlib import Path

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"


def _load_handler(handler_spec: str, plugin_root: str):
    """Load a Python function from 'file.py:function_name' spec."""
    file_part, func_part = handler_spec.split(":", 1)
    abs_path = os.path.join(plugin_root, file_part)
    if not os.path.exists(abs_path):
        raise ImportError(f"Handler file not found: {abs_path}")
    spec = importlib.util.spec_from_file_location(f"plugin_{func_part}", abs_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, func_part)


def discover_plugins() -> dict:
    """Scan plugins/ directory for plugin.json files. Returns {name: manifest}."""
    plugins = {}
    if not PLUGINS_DIR.exists():
        return plugins
    for d in PLUGINS_DIR.iterdir():
        if not d.is_dir():
            continue
        manifest_path = d / "plugin.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["_root"] = str(d)
            plugins[manifest.get("name", d.name)] = manifest
        except Exception as e:
            print(f"[PluginManager] Failed to load {d.name}: {e}")
    return plugins


def load_plugin_tools(manifest: dict) -> list:
    """Load tool handlers from a plugin manifest. Returns list of tool dicts."""
    from tool_registry import PluginTool  # lazy import

    plugin_root = manifest["_root"]
    tools = []
    for tdef in manifest.get("tools", []):
        try:
            handler = _load_handler(tdef["handler"], plugin_root)
        except Exception as e:
            print(f"[PluginManager] Failed to load tool '{tdef.get('name')}': {e}")
            continue
        tool = type(tdef["name"], (PluginTool,), {
            "name": tdef["name"],
            "description": tdef.get("description", ""),
            "parameters": tdef.get("inputSchema", {"type": "object", "properties": {}}),
            "_handler": staticmethod(handler),
        })()
        tools.append(tool)
    return tools


def load_plugin_hooks(manifest: dict) -> dict:
    """Load hook handlers from a plugin manifest. Returns {event: [handlers]}."""
    plugin_root = manifest["_root"]
    hooks = {}
    for event, handler_specs in manifest.get("hooks", {}).items():
        for spec in handler_specs:
            try:
                handler = _load_handler(spec, plugin_root)
                hooks.setdefault(event, []).append(handler)
            except Exception as e:
                print(f"[PluginManager] Failed to load hook '{spec}': {e}")
    return hooks


def install_plugin(source: str, name: str = "") -> str:
    """Install a plugin from a local path or GitHub URL."""
    target_name = name or os.path.basename(source.rstrip("/\\"))
    target_dir = PLUGINS_DIR / target_name
    if target_dir.exists():
        return f"Plugin '{target_name}' already installed."

    if source.startswith("http://") or source.startswith("https://") or source.startswith("git@"):
        # GitHub URL
        import subprocess
        target_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth", "1", source, str(target_dir)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            shutil.rmtree(target_dir, ignore_errors=True)
            return f"Failed to clone: {result.stderr.strip() or result.stdout.strip()}"
    else:
        # Local path
        src = Path(source).resolve()
        if not src.exists():
            return f"Source not found: {source}"
        if src.is_dir():
            shutil.copytree(src, target_dir)
        else:
            target_dir.mkdir(parents=True)
            shutil.copy2(src, target_dir / f"{target_name}.py")

    # Validate
    manifest_path = target_dir / "plugin.json"
    if not manifest_path.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
        return f"No plugin.json found in installed plugin."

    return f"Plugin '{target_name}' installed successfully."


def uninstall_plugin(name: str) -> str:
    """Remove a plugin by name."""
    target_dir = PLUGINS_DIR / name
    if not target_dir.exists():
        return f"Plugin '{name}' not found."
    shutil.rmtree(target_dir)
    return f"Plugin '{name}' uninstalled successfully."


def list_plugins() -> list[dict]:
    """List all discovered plugins with their metadata."""
    plugins = discover_plugins()
    result = []
    for name, manifest in plugins.items():
        result.append({
            "name": name,
            "version": manifest.get("version", "?"),
            "description": manifest.get("description", ""),
            "tools": len(manifest.get("tools", [])),
            "hooks": list(manifest.get("hooks", {}).keys()),
        })
    return result
