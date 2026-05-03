import os
import json
import tempfile
import shutil
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def _skill_registry_path() -> Path:
    return SKILLS_DIR / "registry.json"


def load_registry() -> list[dict]:
    path = _skill_registry_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_registry(entries: list[dict]):
    entries.sort(key=lambda e: e.get("name", ""))
    _skill_registry_path().write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def install_skill_from_path(source: str, name: str = "") -> str:
    """Install a skill from a local directory or .md file path."""
    src = Path(source)
    if not src.exists():
        return f"Error: path not found: {source}"
    if src.is_file() and src.suffix == ".md":
        skill_name = name or src.stem
        dest = SKILLS_DIR / "public" / f"{skill_name}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))
    elif src.is_dir():
        skill_name = name or src.name
        dest = SKILLS_DIR / "public" / skill_name
        if dest.exists():
            shutil.rmtree(str(dest))
        shutil.copytree(str(src), str(dest))
    else:
        return f"Error: unsupported source type: {source}"
    registry = load_registry()
    entry = next((e for e in registry if e.get("name") == skill_name), None)
    if entry:
        entry["source"] = str(source)
    else:
        registry.append({"name": skill_name, "source": str(source), "type": "local"})
    save_registry(registry)
    return f"Installed skill: {skill_name}"


def install_skill_from_url(url: str, name: str = "") -> str:
    """Install a skill from a URL (raw .md file or GitHub repo)."""
    import urllib.request
    skill_name = name or Path(url).stem
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Error fetching URL: {e}"
    dest = SKILLS_DIR / "public" / f"{skill_name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    registry = load_registry()
    entry = next((e for e in registry if e.get("name") == skill_name), None)
    if entry:
        entry["source"] = url
    else:
        registry.append({"name": skill_name, "source": url, "type": "remote"})
    save_registry(registry)
    return f"Installed skill from URL: {skill_name}"


def search_registry(query: str) -> list[dict]:
    """Search installed and available skills."""
    registry = load_registry()
    q = query.lower()
    results = []
    for entry in registry:
        if q in entry.get("name", "").lower():
            results.append(entry)
    for f in (SKILLS_DIR / "public").iterdir():
        if f.suffix == ".md" and q in f.stem.lower():
            name = f.stem
            if not any(r.get("name") == name for r in results):
                results.append({"name": name, "source": str(f), "type": "local"})
    return results
