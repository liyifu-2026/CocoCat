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
        user_id = params.get("user_id", "")
        if not prompt:
            return {"error": "no prompt provided"}
        if params.get("stream_progress"):
            def _p(msg):
                line = json.dumps({"event": "progress", "content": msg}, ensure_ascii=False)
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
            result = agent_loop.run(prompt, user_id=user_id, on_progress=_p)
        else:
            result = agent_loop.run(prompt, user_id=user_id)
        return result
    elif method == "task_stream":
        if agent_loop is None:
            return {"error": "agent loop not initialized"}
        prompt = params.get("prompt", "")
        user_id = params.get("user_id", "")
        if not prompt:
            return {"error": "no prompt provided"}

        def _progress(msg):
            line = json.dumps({"event": "progress", "content": msg}, ensure_ascii=False)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

        _progress("Running full ReAct loop with tools...")

        result = agent_loop.run(prompt, user_id=user_id, on_progress=_progress)
        content = result.get("content", str(result))

        sys.stdout.write(json.dumps({"event": "progress", "content": "Streaming response..."}) + "\n")
        sys.stdout.flush()

        words = content.split(" ")
        for word in words:
            chunk = word + " "
            line = json.dumps({"event": "delta", "content": chunk}, ensure_ascii=False)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

        sys.stdout.write(json.dumps({"event": "progress", "content": "Response complete"}) + "\n")
        line = json.dumps({"event": "done", "content": content}, ensure_ascii=False)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
        return {"content": content, "streamed": True}
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

    # Start heartbeat for schedule-based execution
    if IDENTITY.get("id"):
        from heartbeat import start_heartbeat
        start_heartbeat(IDENTITY["id"], IDENTITY.get("name", "Agent"), interval=300,
                        scene=IDENTITY.get("scene", "default"))

    agent_loop = None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        req_id = None
        try:
            request = json.loads(line)
            req_id = request.get("id")

            if request.get("method") in ("task", "task_stream") and agent_loop is None:
                from agent_runner import AgentRunner

                agent_id = IDENTITY.get("id") or "unknown"
                runner = AgentRunner(
                    agent_id=agent_id,
                    agent_name=IDENTITY.get("name") or "Agent",
                    scene=IDENTITY.get("scene", "default"),
                )
                runner._ensure_loop()
                agent_loop = runner._loop

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
