"""CocoCat Agent Runtime v2 — stateless stdio JSON-RPC server."""
import sys
import json
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _write_stream(etype: str, **kwargs):
    data = {"type": etype}
    data.update(kwargs)
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()


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
        history = params.get("history", [])
        result = agent_loop.run(content, user_id=params.get("user_id", ""), history=history)
        if isinstance(result, dict):
            return result
        return {"response": str(result)}

    elif method == "shutdown":
        return {"shutdown": True}

    else:
        return {"error": f"unknown method: {method}"}


def main():
    import argparse
    import compileall

    # Pre-compile Python files for faster cold start
    compileall.compile_dir(os.path.dirname(os.path.abspath(__file__)),
                           force=False, quiet=1)

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

            if request.get("method") == "chat":
                params = request.get("params", {})
                if agent_loop is None:
                    raise RuntimeError("agent loop not initialized")
                content = params.get("content", "")

                def on_progress(msg):
                    _write_stream("progress", content=msg)
                def on_tool(name, input_data, status, result=""):
                    _write_stream("tool", name=name,
                        input=str(input_data)[:500], status=status,
                        result=str(result)[:500])
                def on_reasoning(msg):
                    if msg:
                        _write_stream("reasoning", content=msg)

                result = agent_loop.run(
                    content,
                    user_id=params.get("user_id", ""),
                    on_progress=on_progress,
                    on_tool=on_tool,
                    on_reasoning=on_reasoning,
                )
                if not isinstance(result, dict):
                    result = {"response": str(result)}
                response = {"jsonrpc": "2.0", "result": result, "id": req_id}
            elif request.get("method") == "process_kb_source":
                params = request.get("params", {})
                kb_name = params.get("kb_name", "")
                filename = params.get("filename", "")
                source_path = params.get("source_path", "")
                extracted_path = params.get("extracted_path", "")
                if agent_loop is None:
                    raise RuntimeError("agent loop not initialized")

                def write_progress(msg):
                    _write_stream("progress", content=msg)
                def write_tool(name, input_data, status, result=""):
                    _write_stream("tool", name=name,
                        input=str(input_data)[:500], status=status,
                        result=str(result)[:500])
                def write_reasoning(msg):
                    if msg:
                        _write_stream("reasoning", content=msg)

                read_path = extracted_path or source_path
                prompt = (
                    f"A new source file has been uploaded to the knowledge base '{kb_name}'. "
                    f"File: {filename}\n\n"
                    f"Read the extracted text at {read_path}, then follow the Knowledge Ingestion skill "
                    f"to process it into wiki pages. "
                    f"Read skills/public/knowledge-ingestion.md for the exact workflow."
                )
                result = agent_loop.run(
                    prompt,
                    user_id=params.get("user_id", ""),
                    on_progress=write_progress,
                    on_tool=write_tool,
                    on_reasoning=write_reasoning,
                )
                if not isinstance(result, dict):
                    result = {"response": str(result)}
                response = {"jsonrpc": "2.0", "result": result, "id": req_id}
            else:
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
