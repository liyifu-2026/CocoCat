"""CocoCat Agent Runtime v2 — stateless stdio JSON-RPC server."""
import sys
import json
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def handle_request(request: dict, agent_loop=None) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "ping":
        return {"pong": True, "agent_id": params.get("agent_id", "unknown")}

    elif method == "identify":
        return {"agent_id": params.get("agent_id")}

    elif method == "chat":
        if agent_loop is None:
            return {"error": "agent loop not initialized"}
        content = params.get("content", "")
        messages = params.get("messages", [])
        result = agent_loop.run(content, user_id=params.get("user_id", ""))
        if isinstance(result, dict):
            return result
        return {"response": str(result)}

    elif method == "shutdown":
        return {"shutdown": True}

    else:
        return {"error": f"unknown method: {method}"}


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-id", default=None)
    parser.add_argument("--model", default="gpt-4")
    parser.add_argument("--scene-id", default="default")
    args, _ = parser.parse_known_args()

    # Eagerly initialize agent loop on startup, not on first request.
    # This loads tools, plugins, scene context before accepting any RPC.
    from agent_runner import AgentRunner
    runner = AgentRunner(
        agent_id=args.agent_id or "unknown",
        agent_name=args.agent_id or "Agent",
        scene=args.scene_id,
    )
    runner._ensure_loop()
    agent_loop = runner._loop
    del runner

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        request = None
        req_id = None
        try:
            request = json.loads(line)
            req_id = request.get("id")

            result = handle_request(request, agent_loop=agent_loop)
            response = {"jsonrpc": "2.0", "result": result, "id": req_id}
        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
                "id": None,
            }
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

        if request and request.get("method") == "shutdown":
            break


if __name__ == "__main__":
    main()
