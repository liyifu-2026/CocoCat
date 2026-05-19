"""Test that pin/recall and load_memory_from_agent_dir use consistent paths."""
import os
import pytest
from cococat.core.tools import create_core_tools, ToolRegistry
from cococat.core.agent_builder import load_memory_from_agent_dir


class TestMemoryPathAlignment:
    @pytest.mark.asyncio
    async def test_pin_writes_to_pinned_md_at_agent_dir(self, tmp_path):
        """Pin writes to {agent_dir}/pinned.md — same file load_memory_from_agent_dir reads."""
        agent_dir = str(tmp_path / "agents" / "main")

        tools = create_core_tools()
        reg = ToolRegistry(tools)
        ctx = {"agent_dir": agent_dir}

        await reg.execute("pin", {"fact": "user prefers dark mode"}, ctx)
        await reg.execute("pin", {"fact": "project is CocoCat"}, ctx)

        _, pinned_content, _ = load_memory_from_agent_dir(agent_dir)
        assert "user prefers dark mode" in pinned_content
        assert "project is CocoCat" in pinned_content

    @pytest.mark.asyncio
    async def test_recall_finds_pinned_facts(self, tmp_path):
        """Recall searches the same pinned.md that pin writes to."""
        agent_dir = str(tmp_path / "agents" / "main")
        os.makedirs(agent_dir, exist_ok=True)

        pinned_path = os.path.join(agent_dir, "pinned.md")
        with open(pinned_path, "w") as f:
            f.write("user likes python\nuser from Beijing\n")

        tools = create_core_tools()
        reg = ToolRegistry(tools)
        ctx = {"agent_dir": agent_dir}

        result = await reg.execute("recall", {"query": "Beijing"}, ctx)
        assert "Beijing" in result

    @pytest.mark.asyncio
    async def test_pin_default_path_is_pinned_md(self, tmp_path):
        """Without explicit memory_path, pin writes to {agent_dir}/pinned.md."""
        agent_dir = str(tmp_path / "agents" / "main")

        tools = create_core_tools()
        reg = ToolRegistry(tools)
        ctx = {"agent_dir": agent_dir}

        await reg.execute("pin", {"fact": "default path test"}, ctx)

        _, pinned_content, _ = load_memory_from_agent_dir(agent_dir)
        assert "default path test" in pinned_content
