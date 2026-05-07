from agent_loop import AgentLoop
from tools import create_default_registry
from context import load_scene_context, load_env_skills, load_agent_memory


class AgentRunner:
    """Unified facade over AgentLoop setup and execution (nanobot Nanobot pattern)."""

    def __init__(self, agent_id: str, agent_name: str = "Agent", scene: str = "default",
                 model: str = "", agent_runtime_path: str = "", bus=None):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.scene = scene
        self.model = model
        self.bus = bus
        if not agent_runtime_path:
            import os
            agent_runtime_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_runtime.py")
        self.agent_runtime_path = agent_runtime_path
        self._loop: AgentLoop | None = None

    def _ensure_loop(self):
        if self._loop is not None:
            return
        scene_name, scene_context = load_scene_context(self.scene)
        scene_skills = load_env_skills(self.scene)
        tools = create_default_registry(
            agent_runtime_path=self.agent_runtime_path,
            scene_id=self.scene, agent_id=self.agent_id, agent_name=self.agent_name,
        )
        llm_provider = None
        if self.model:
            from providers import make_provider
            llm_provider = make_provider(self.model)
        self._loop = AgentLoop(
            agent_id=self.agent_id, agent_name=self.agent_name, tools=tools,
            scene_name=scene_name, scene_context=scene_context, scene_skills=scene_skills,
            llm=llm_provider,
        )

    def run(self, prompt: str, user_id: str = "") -> dict:
        self._ensure_loop()
        return self._loop.run(prompt, user_id=user_id)
