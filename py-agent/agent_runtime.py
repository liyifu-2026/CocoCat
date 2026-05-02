"""CocoCat Agent Runtime — capable agent with LLM + tools + sub-agents."""
import sys
import json
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

IDENTITY = {"id": None, "name": "unknown", "scene": "default"}


def handle_request(request: dict, agent_loop=None) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "ping":
        return {"pong": True, "agent": "cococat-capable"}
    elif method == "echo":
        return params
    elif method == "identify":
        return dict(IDENTITY)
    elif method == "task":
        if agent_loop is None:
            return {"error": "agent loop not initialized"}
        prompt = params.get("prompt", "")
        if not prompt:
            return {"error": "no prompt provided"}
        result = agent_loop.run(prompt)
        return result
    else:
        raise ValueError(f"Method not found: {method}")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default=None)
    parser.add_argument("--name", default="unknown")
    parser.add_argument("--scene", default="default")
    args, _ = parser.parse_known_args()
    if args.id:
        IDENTITY["id"] = args.id
        IDENTITY["name"] = args.name
        IDENTITY["scene"] = args.scene

    agent_loop = None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        req_id = None
        try:
            request = json.loads(line)
            req_id = request.get("id")

            if request.get("method") == "task" and agent_loop is None:
                from agent_loop import AgentLoop
                from tools import create_default_registry
                from context import load_scene_context, load_env_skills

                script_dir = os.path.dirname(os.path.abspath(__file__))
                agent_runtime_path = os.path.join(script_dir, "agent_runtime.py")

                scene_name, scene_context = load_scene_context(IDENTITY.get("scene", "default"))
                scene_skills = load_env_skills(IDENTITY.get("scene", "default"))

                current_scene = IDENTITY.get("scene", "default")
                agent_id = IDENTITY.get("id") or "unknown"
                tools = create_default_registry(
                    agent_runtime_path=agent_runtime_path,
                    scene_id=current_scene,
                    agent_id=agent_id,
                    agent_name=IDENTITY.get("name") or "Agent",
                )
                agent_loop = AgentLoop(
                    agent_id=agent_id,
                    agent_name=IDENTITY.get("name") or "Agent",
                    tools=tools,
                    scene_name=scene_name,
                    scene_context=scene_context,
                    scene_skills=scene_skills,
                )

            result = handle_request(request, agent_loop=agent_loop)
            response = {"jsonrpc": "2.0", "result": result, "id": req_id}
        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
                "id": None,
            }
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
