"""KB Knowledge Graph — relevance scoring, community detection, insights."""

from __future__ import annotations

import logging
from collections import defaultdict, Counter
from typing import Any

from cococat.ingest.merge import parse_frontmatter

logger = logging.getLogger("cococat.ingest.graph")


class KnowledgeGraph:
    """Analyzes wiki page relationships for insights.

    Graph built from: direct links (wikilinks), related frontmatter,
    source overlap, type affinity.
    """

    def __init__(self, kb_dir: str):
        self._kb_dir = kb_dir
        self._pages: dict[str, dict] = {}  # slug → {path, fm, body, links, type}
        self._edges: dict[tuple[str, str], float] = {}  # (a, b) → weight
        self._build()

    def _build(self) -> None:
        """Build graph from wiki pages."""
        import os, re
        wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
        wiki_dir = os.path.join(self._kb_dir, "wiki")
        if not os.path.isdir(wiki_dir):
            return

        # First pass: collect all pages
        for root, _, files in os.walk(wiki_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                path = os.path.join(root, fname)
                slug = fname[:-3]
                with open(path, encoding="utf-8") as f:
                    fm, body = parse_frontmatter(f.read())

                links = set(wikilink_re.findall(body))
                links.update(fm.get("related", []) or [])

                self._pages[slug] = {
                    "path": path,
                    "slug": slug,
                    "fm": fm,
                    "body": body,
                    "links": links,
                    "sources": set(fm.get("sources", []) or []),
                    "type": fm.get("type", ""),
                }

        # Second pass: calculate edge weights using 4-signal scoring
        slugs = list(self._pages.keys())
        for i, a in enumerate(slugs):
            for b in slugs[i + 1:]:
                weight = self._edge_weight(a, b)
                if weight > 0:
                    self._edges[(a, b)] = weight

    def _edge_weight(self, a: str, b: str) -> float:
        """4-signal relevance scoring between two pages."""
        pa = self._pages[a]
        pb = self._pages[b]

        # Signal 1: Direct links (×3.0)
        direct = 0.0
        if a in pb["links"] or b in pa["links"]:
            direct = 3.0

        # Signal 2: Source overlap (×4.0)
        source_overlap = 0.0
        shared = pa["sources"] & pb["sources"]
        if shared:
            source_overlap = 4.0 * len(shared) / max(len(pa["sources"] | pb["sources"]), 1)

        # Signal 3: Adamic-Adar (×1.5) — shared neighbors
        shared_neighbors = len(
            (pa["links"] & set(self._pages.keys())) &
            (pb["links"] & set(self._pages.keys()))
        )
        adamic_adar = 0.0
        if shared_neighbors > 0:
            adamic_adar = 1.5 / (1.0 / max(shared_neighbors, 1))

        # Signal 4: Type affinity (×1.0)
        type_affinity = 1.0 if pa["type"] == pb["type"] and pa["type"] else 0.0

        return direct + source_overlap + adamic_adar + type_affinity

    def insights(self) -> dict[str, Any]:
        """Return graph insights: surprising connections, gaps, bridges."""
        if len(self._pages) < 3:
            return {"connections": [], "gaps": [], "bridges": []}

        # Sort edges by weight
        sorted_edges = sorted(self._edges.items(), key=lambda x: -x[1])

        # Surprising connections: high-weight edges between pages with no direct links
        connections = []
        for (a, b), w in sorted_edges[:10]:
            pa = self._pages[a]
            pb = self._pages[b]
            has_direct = a in pb["links"] or b in pa["links"]
            if w >= 3.0 and not has_direct:
                connections.append({
                    "from": a, "to": b, "weight": round(w, 2),
                    "reason": "source_overlap" if w >= 4.0 else "shared_neighbors",
                })

        # Knowledge gaps: pages with few/no connections
        degrees = Counter()
        for (a, b), w in self._edges.items():
            degrees[a] += w
            degrees[b] += w
        gaps = [
            {"slug": s, "connections": round(degrees.get(s, 0), 1)}
            for s in self._pages
            if degrees.get(s, 0) < 1.0
        ]

        # Bridge nodes: pages with high betweenness (simplified: many connections + different types)
        bridge_candidates = []
        for slug, info in self._pages.items():
            neighbor_types = set()
            for (a, b), _ in self._edges.items():
                other = b if a == slug else (a if b == slug else None)
                if other and other in self._pages:
                    neighbor_types.add(self._pages[other]["type"])
            if len(neighbor_types) >= 2 and degrees.get(slug, 0) >= 3.0:
                bridge_candidates.append({
                    "slug": slug,
                    "weight": round(degrees.get(slug, 0), 1),
                    "connects_types": list(neighbor_types),
                })

        bridge_candidates.sort(key=lambda x: -x["weight"])

        return {
            "connections": connections[:5],
            "gaps": gaps[:10],
            "bridges": bridge_candidates[:5],
        }

    def to_d3(self) -> dict:
        """Export graph in D3.js format {nodes: [...], links: [...]}."""
        nodes = [{"id": s, "type": self._pages[s].get("type", ""),
                   "title": self._pages[s].get("fm", {}).get("title", s)}
                  for s in self._pages]
        links = [{"source": a, "target": b, "value": round(w, 2)}
                 for (a, b), w in self._edges.items()]
        return {"nodes": nodes, "links": links}
