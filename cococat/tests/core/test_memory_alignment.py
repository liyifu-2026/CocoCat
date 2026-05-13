"""Test that pin/recall and load_memory_from_agent_dir use the same path."""
import os
import pytest
from cococat.core.tools import create_core_tools, ToolRegistry
from cococat.prompt import load_memory_from_agent_dir


class TestMemoryPathAlignment:
    @pytest.mark.asyncio
    async def test_pin_writes_to_agent_memory_subdir(self, tmp_path):
        """Pin writes to {agent_dir}/memory/memory.md — same path load_memory_from_agent_dir reads."""
        agent_dir = str(tmp_path / "agents" / "main")

        tools = create_core_tools()
        reg = ToolRegistry(tools)
        ctx = {"agent_dir": agent_dir}

        await reg.execute("pin", {"fact": "user prefers dark mode"}, ctx)
        await reg.execute("pin", {"fact": "project is CocoCat"}, ctx)

        memory_content, _ = load_memory_from_agent_dir(agent_dir)
        assert "user prefers dark mode" in memory_content
        assert "project is CocoCat" in memory_content

    @pytest.mark.asyncio
    async def test_recall_finds_pinned_facts(self, tmp_path):
        """Recall searches the same memory.md that pin writes to."""
        agent_dir = str(tmp_path / "agents" / "main")
        mem_dir = os.path.join(agent_dir, "memory")
        os.makedirs(mem_dir, exist_ok=True)
        mem_path = os.path.join(mem_dir, "memory.md")
        with open(mem_path, "w") as f:
            f.write("user likes python\nuser from Beijing\n")

        tools = create_core_tools()
        reg = ToolRegistry(tools)
        ctx = {"agent_dir": agent_dir}

        result = await reg.execute("recall", {"query": "Beijing"}, ctx)
        assert "Beijing" in result

    @pytest.mark.asyncio
    async def test_pin_default_path_is_memory_subdir(self, tmp_path):
        """Without explicit memory_path, pin writes to agents/main/memory/memory.md."""
        agent_dir = str(tmp_path / "agents" / "main")

        tools = create_core_tools()
        reg = ToolRegistry(tools)
        # Simulate what agent.run() should pass
        ctx = {"agent_dir": agent_dir}

        await reg.execute("pin", {"fact": "default path test"}, ctx)

        # Should be loadable by load_memory_from_agent_dir (same path)
        memory_content, _ = load_memory_from_agent_dir(agent_dir)
        assert "default path test" in memory_content

