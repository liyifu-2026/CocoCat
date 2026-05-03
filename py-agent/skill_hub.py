import os
import sys
import json
import tempfile
import shutil
import re
import time
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
    version = (entry.get("version", 0) if entry else 0) + 1
    if entry:
        entry["source"] = str(source)
        entry["version"] = version
        entry["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        registry.append({
            "name": skill_name, "source": str(source), "type": "local",
            "version": 1, "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
    save_registry(registry)
    return f"Installed skill: {skill_name} (v{version})"


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
    version = (entry.get("version", 0) if entry else 0) + 1
    if entry:
        entry["source"] = url
        entry["version"] = version
        entry["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        registry.append({
            "name": skill_name, "source": url, "type": "remote",
            "version": 1, "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
    save_registry(registry)
    return f"Installed skill from URL: {skill_name} (v{version})"


def validate_skill(name: str) -> str:
    """Validate that a skill file has the required # Skill: header."""
    skill_file = SKILLS_DIR / "public" / f"{name}.md"
    if not skill_file.exists():
        return f"Error: skill '{name}' not found"
    content = skill_file.read_text(encoding="utf-8")
    if not re.search(r"^# Skill:\s+\S", content, re.MULTILINE):
        return f"Warning: skill '{name}' missing '# Skill:' header"
    return f"Skill '{name}' is valid"


def parse_skill_metadata(content: str) -> dict:
    """Parse YAML frontmatter from skill markdown content."""
    m = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
    if not m:
        return {}
    fm = m.group(1)
    metadata = {}
    for line in fm.split("\n"):
        line = line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            metadata[key] = val
    requires_match = re.search(r"requires:\n((?:\s+.*\n?)*)", content)
    if requires_match:
        requires = {}
        for rline in requires_match.group(1).split("\n"):
            rline = rline.strip()
            if rline.startswith("- "):
                continue
            if ":" in rline:
                rk, rv = rline.split(":", 1)
                requires[rk.strip()] = [x.strip().strip('"') for x in rv.split(",")]
        metadata["requires"] = requires
    return metadata


def check_skill_dependencies(skill_name: str) -> tuple[bool, list[str]]:
    """Check if a skill's dependencies are met. Returns (ok, missing_reasons)."""
    base = Path(__file__).resolve().parent.parent
    for subdir in ["skills/public", "skills/private"]:
        skill_path = base / subdir / f"{skill_name}.md"
        if skill_path.exists():
            content = skill_path.read_text(encoding="utf-8")
            meta = parse_skill_metadata(content)
            break
    else:
        return True, []

    missing = []
    requires = meta.get("requires", {})

    for bin_name in requires.get("bins", []):
        if not shutil.which(bin_name):
            missing.append(f"Missing binary: {bin_name}")

    for env_var in requires.get("env", []):
        if not os.environ.get(env_var):
            missing.append(f"Missing env var: {env_var}")

    platform_req = meta.get("platform", "")
    if platform_req and platform_req != sys.platform:
        missing.append(f"Requires platform: {platform_req}, current: {sys.platform}")

    return len(missing) == 0, missing


def get_skill_summary(skill_name: str) -> str:
    """Get a one-line summary of a skill (first line after frontmatter)."""
    base = Path(__file__).resolve().parent.parent
    for subdir in ["skills/public", "skills/private"]:
        skill_path = base / subdir / f"{skill_name}.md"
        if skill_path.exists():
            content = skill_path.read_text(encoding="utf-8")
            body = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL).strip()
            first_line = body.split("\n")[0].strip()
            return first_line.lstrip("#").strip()
    return skill_name


def search_marketplace(query: str) -> list[dict]:
    """Search for skills in the local registry and known remote sources."""
    results = []
    for entry in load_registry():
        if query.lower() in entry.get("name", "").lower() or query.lower() in entry.get("description", "").lower():
            results.append(entry)
    base = Path(__file__).resolve().parent.parent
    public_dir = base / "skills" / "public"
    if public_dir.exists():
        for f in public_dir.iterdir():
            if f.suffix == ".md":
                if query.lower() in f.stem.lower():
                    meta = parse_skill_metadata(f.read_text(encoding="utf-8"))
                    results.append({
                        "name": f.stem,
                        "description": meta.get("description", ""),
                        "source": str(f),
                        "type": "local",
                    })
    return results


def uninstall_skill(name: str) -> str:
    """Remove a skill from the filesystem and registry."""
    skill_file = SKILLS_DIR / "public" / f"{name}.md"
    if skill_file.exists():
        skill_file.unlink()
    skill_dir = SKILLS_DIR / "public" / name
    if skill_dir.exists():
        shutil.rmtree(str(skill_dir))
    registry = load_registry()
    registry = [e for e in registry if e.get("name") != name]
    save_registry(registry)
    return f"Uninstalled skill: {name}"


def list_installed_skills() -> list[dict]:
    """List all installed skills with version info."""
    registry = load_registry()
    if registry:
        return registry
    results = []
    for f in sorted((SKILLS_DIR / "public").iterdir()):
        if f.suffix == ".md":
            results.append({"name": f.stem, "source": str(f), "type": "local", "version": 0})
    return results


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
