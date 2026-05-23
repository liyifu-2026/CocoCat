"""KnowledgeService — KB directory operations extracted from route handlers."""

import os


class KnowledgeService:
    """Encapsulates knowledge base file system operations."""

    def __init__(self, knowledge_dir: str):
        self._knowledge_dir = knowledge_dir

    def _kb_path(self, kb_name: str) -> str:
        return os.path.join(self._knowledge_dir, kb_name)

    def list_kbs(self) -> list[dict]:
        if not os.path.isdir(self._knowledge_dir):
            return []
        kbs = []
        for name in os.listdir(self._knowledge_dir):
            path = os.path.join(self._knowledge_dir, name)
            if os.path.isdir(path) and not name.startswith("."):
                purpose = ""
                purpose_path = os.path.join(path, "purpose.md")
                if os.path.exists(purpose_path):
                    with open(purpose_path, encoding="utf-8") as f:
                        purpose = f.read(300)
                kbs.append({"id": name, "purpose": purpose})
        return kbs

    def create_kb(self, name: str, purpose: str = "") -> str:
        base = self._kb_path(name)
        if os.path.exists(os.path.join(base, "wiki")):
            return f"Knowledge base '{name}' already exists"
        dirs = [
            os.path.join(base, "wiki", "entities"),
            os.path.join(base, "wiki", "concepts"),
            os.path.join(base, "raw", "sources"),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
        with open(os.path.join(base, "purpose.md"), "w", encoding="utf-8") as f:
            f.write(f"# {name}\n\n{purpose or 'Knowledge base for ' + name}\n")
        with open(os.path.join(base, "index.md"), "w", encoding="utf-8") as f:
            f.write(f"# {name} Index\n\n## Entities\n\n## Concepts\n")
        with open(os.path.join(base, "log.md"), "w", encoding="utf-8") as f:
            f.write(f"# {name} Change Log\n\n")
        return ""

    def save_upload(self, kb_name: str, filename: str, content: bytes) -> str:
        kb_dir = self._kb_path(kb_name)
        raw_dir = os.path.join(kb_dir, "raw", "sources")
        os.makedirs(raw_dir, exist_ok=True)
        file_path = os.path.join(raw_dir, filename or "upload.bin")
        with open(file_path, "wb") as f:
            f.write(content)
        return file_path

    def wiki_index(self, kb_name: str) -> tuple[list[str], list[str]]:
        kb_path = self._kb_path(kb_name)
        entities = self._list_md_files(os.path.join(kb_path, "wiki", "entities"))
        concepts = self._list_md_files(os.path.join(kb_path, "wiki", "concepts"))
        return entities, concepts

    def wiki_page(self, kb_name: str, page_type: str, page_name: str) -> dict | None:
        path = os.path.join(self._kb_path(kb_name), "wiki", page_type, f"{page_name}.md")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            content = f.read(10000)
        return {"name": page_name, "type": page_type, "content": content}

    def search(self, kb_name: str, query: str) -> list[dict]:
        wiki_dir = os.path.join(self._kb_path(kb_name), "wiki")
        if not os.path.isdir(wiki_dir) or not query:
            return []
        results = []
        for root, _, files in os.walk(wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                with open(path, encoding="utf-8") as f:
                    content = f.read(5000)
                if query.lower() in content.lower():
                    rel = os.path.relpath(root, wiki_dir)
                    results.append({
                        "name": fname[:-3],
                        "type": rel,
                        "snippet": content[:200],
                    })
        return results[:20]

    @staticmethod
    def _list_md_files(path: str) -> list[str]:
        if not os.path.isdir(path):
            return []
        return sorted(
            f[:-3] for f in os.listdir(path) if f.endswith(".md") and not f.startswith(".")
        )
