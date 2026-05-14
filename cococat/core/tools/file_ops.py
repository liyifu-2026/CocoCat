"""File operation tools — read, write, edit, list, glob, grep."""
import os


def _read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        if offset:
            lines = lines[offset:]
        if limit:
            lines = lines[:limit]
        return "".join(lines)
    except Exception as e:
        return f"Error reading {path}: {e}"


def _write_file(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


def _edit_file(path: str, old_str: str, new_str: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if old_str not in content:
            return f"Error: old string not found in {path}"
        content = content.replace(old_str, new_str, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Edited {path}"
    except Exception as e:
        return f"Error editing {path}: {e}"


def _list_dir(path: str) -> str:
    try:
        items = os.listdir(path)
        items.sort()
        return "\n".join(items)
    except Exception as e:
        return f"Error listing {path}: {e}"


def _glob(pattern: str) -> str:
    if not pattern:
        return "Error: 'pattern' is required"
    import glob as glob_mod
    try:
        matches = glob_mod.glob(pattern, recursive=True)
        matches.sort()
        return "\n".join(matches) if matches else ""
    except Exception as e:
        return f"Error glob: {e}"


def _grep(pattern: str, path: str) -> str:
    if not pattern:
        return "Error: 'pattern' is required"
    import subprocess
    try:
        cmd = ["grep", "-rn", pattern, path] if path else ["grep", "-rn", pattern, "."]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip() or "No matches found"
    except subprocess.TimeoutExpired:
        return "Error: grep timed out (30s)"
    except Exception as e:
        return f"Error: {e}"
