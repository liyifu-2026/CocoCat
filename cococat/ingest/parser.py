"""KB ingest parser — parses ---FILE:path--- blocks from LLM output."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Match ---FILE: /path/to/file --- or --- FILE: /path --- variations
_FILE_START = re.compile(r"^---\s*FILE:\s*(.+?)\s*---\s*$", re.MULTILINE)
_FILE_END = re.compile(r"^---\s*END\s*FILE\s*---\s*$", re.MULTILINE)


@dataclass
class FileBlock:
    path: str
    content: str


def is_safe_ingest_path(path: str) -> bool:
    """Reject path traversal and absolute paths."""
    # No .. sequences
    if ".." in path.replace("\\", "/").split("/"):
        return False
    # No absolute paths
    if path.startswith("/") or path.startswith("\\"):
        return False
    # No null bytes / control chars
    if "\x00" in path or any(ord(c) < 32 for c in path):
        return False
    # Must have a .md extension
    if not path.endswith(".md"):
        return False
    return True


def parse_file_blocks(text: str) -> list[FileBlock]:
    """Parse ---FILE:path--- ... ---END FILE--- blocks from LLM output.

    Handles:
    - Code fences (---FILE inside ``` is ignored)
    - Stream truncation (unclosed final block is included)
    - Path traversal rejection
    - CRLF normalization
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    blocks = []
    in_fence = False
    current_block: FileBlock | None = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        # Track code fences
        fence_match = re.match(r"^(`{3,})", line)
        if fence_match and not (current_block and line.startswith("---")):
            in_fence = not in_fence
            if current_block:
                current_lines.append(line)
            continue

        if in_fence:
            if current_block:
                current_lines.append(line)
            continue

        # Check for FILE block end
        if _FILE_END.match(line):
            if current_block:
                current_block.content = "\n".join(current_lines).strip()
                blocks.append(current_block)
                current_block = None
                current_lines = []
            continue

        # Check for FILE block start
        m = _FILE_START.match(line)
        if m:
            if current_block:
                # Unclosed previous block — include it
                current_block.content = "\n".join(current_lines).strip()
                blocks.append(current_block)
            path = m.group(1).strip()
            if is_safe_ingest_path(path):
                current_block = FileBlock(path=path, content="")
                current_lines = []
            else:
                current_block = None
                current_lines = []
        elif current_block:
            current_lines.append(line)

    # Handle unclosed final block (stream truncation)
    if current_block and current_lines:
        current_block.content = "\n".join(current_lines).strip()
        blocks.append(current_block)

    return blocks
