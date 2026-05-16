"""KB tool implementations — thin wrappers around KBService."""

from __future__ import annotations

from typing import Any


def _search_kb(params: dict, ctx: dict) -> str:
    """Search a knowledge base."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    query = params.get("query", "")
    if not kb_name or not query:
        return "Error: kb_name and query are required"
    service = get_kb_service()
    results = service.search(kb_name, query)
    if not results:
        return f"No results found for '{query}' in KB '{kb_name}'."
    lines = [f"Search results for '{query}' in KB '{kb_name}':"]
    for i, r in enumerate(results, 1):
        lines.append(f"\n{i}. **{r['name']}** ({r['type']})")
        lines.append(f"   {r['snippet'][:200]}")
    return "\n".join(lines)


def _read_wiki(params: dict, ctx: dict) -> str:
    """Read a wiki page."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    page_type = params.get("type", "entities")
    slug = params.get("slug", "")
    if not kb_name or not slug:
        return "Error: kb_name, type, and slug are required"
    service = get_kb_service()
    page = service.read(kb_name, page_type, slug)
    if page is None:
        return f"Page '{slug}' not found in KB '{kb_name}' ({page_type})."
    return f"# {page['name']} ({page['type']})\n\n{page['content']}"


def _write_wiki(params: dict, ctx: dict) -> str:
    """Write a wiki page (kb-agent only)."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    page_type = params.get("type", "entities")
    slug = params.get("slug", "")
    content = params.get("content", "")
    title = params.get("title", slug)
    if not kb_name or not slug or not content:
        return "Error: kb_name, type, slug, and content are required"
    service = get_kb_service()
    service.write_page(kb_name, page_type, slug, content, {"title": title})
    return f"Page '{slug}' written to KB '{kb_name}' ({page_type})."


def _run_dedup(params: dict, ctx: dict) -> str:
    """Run dedup pipeline (kb-agent only)."""
    import asyncio
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    if not kb_name:
        return "Error: kb_name is required"
    llm = ctx.get("_llm")
    if not llm:
        return "Error: LLM not available for dedup"
    service = get_kb_service()
    result = asyncio.run(service.run_dedup(kb_name, llm))
    return f"Dedup complete for KB '{kb_name}': {result}"


def _run_lint(params: dict, ctx: dict) -> str:
    """Run health check (kb-agent only)."""
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    if not kb_name:
        return "Error: kb_name is required"
    service = get_kb_service()
    result = service.run_lint(kb_name)
    lines = [f"Lint results for KB '{kb_name}':"]
    for key, val in result.items():
        if isinstance(val, list) and val:
            lines.append(f"- {key}: {len(val)} issues")
            for item in val[:5]:
                lines.append(f"  • {item}")
    if not any(isinstance(v, list) and v for v in result.values()):
        lines.append("No issues found.")
    return "\n".join(lines)


def _gen_overview(params: dict, ctx: dict) -> str:
    """Generate overview (kb-agent only)."""
    import asyncio
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    if not kb_name:
        return "Error: kb_name is required"
    llm = ctx.get("_llm")
    service = get_kb_service()
    overview = asyncio.run(service.gen_overview(kb_name, llm))
    return f"Overview generated for KB '{kb_name}':\n\n{overview[:2000]}"


def _cascade_del(params: dict, ctx: dict) -> str:
    """Cascade delete a source file (kb-agent only)."""
    import asyncio
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    source_filename = params.get("source_filename", "")
    if not kb_name or not source_filename:
        return "Error: kb_name and source_filename are required"
    service = get_kb_service()
    modified = asyncio.run(service.cascade_delete(kb_name, source_filename))
    return f"Cascade delete complete for '{source_filename}' in KB '{kb_name}'. Modified {len(modified)} page(s)."


def _get_graph(params: dict, ctx: dict) -> str:
    """Get knowledge graph data (kb-agent only)."""
    import json
    from cococat.kb.service import get_kb_service
    kb_name = params.get("kb_name", "")
    if not kb_name:
        return "Error: kb_name is required"
    service = get_kb_service()
    data = service.get_graph(kb_name)
    insights = data.get("insights", {})
    lines = [f"Knowledge graph for KB '{kb_name}':"]
    if insights.get("connections"):
        lines.append(f"\nSurprising connections: {json.dumps(insights['connections'], indent=2)}")
    if insights.get("gaps"):
        lines.append(f"\nKnowledge gaps: {json.dumps(insights['gaps'], indent=2)}")
    if insights.get("bridges"):
        lines.append(f"\nBridge nodes: {json.dumps(insights['bridges'], indent=2)}")
    return "\n".join(lines)


def _call_worker(params: dict, ctx: dict) -> str:
    """Call a worker agent for heavy execution (all resident agents)."""
    import asyncio
    task = params.get("task", "")
    if not task:
        return "Error: task is required"
    sub_executor = ctx.get("sub_agent_executor")
    if not sub_executor:
        return "Error: No worker executor available"
    result = asyncio.run(sub_executor(task, ctx.get("agent_id", "unknown")))
    return str(result) if result else "Worker completed, no output."


def _list_kbs(params: dict, ctx: dict) -> str:
    """List all available knowledge bases."""
    import os
    kb_dir = "knowledge"
    if not os.path.isdir(kb_dir):
        return "No knowledge bases found."
    kbs = [n for n in os.listdir(kb_dir)
           if os.path.isdir(os.path.join(kb_dir, n)) and not n.startswith(".")]
    if not kbs:
        return "No knowledge bases found."
    return "Available knowledge bases:\n" + "\n".join(f"- {kb}" for kb in kbs)
