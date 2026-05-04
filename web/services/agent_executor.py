import asyncio
import json

async def execute_agent(agent_runtime_path: str, prompt: str, timeout: int = 60) -> dict:
    request = json.dumps({
        "jsonrpc": "2.0", "method": "task",
        "params": {"prompt": prompt}, "id": 1,
    })
    process = await asyncio.create_subprocess_exec(
        "python", "-u", agent_runtime_path,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=request.encode()),
            timeout=timeout,
        )
        for line in stdout.decode().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
                if "result" in resp:
                    return resp["result"]
                if "error" in resp:
                    return {"error": resp["error"].get("message", "unknown")}
            except json.JSONDecodeError:
                continue
        return {"content": stdout.decode().strip() or "(no output)"}
    except asyncio.TimeoutError:
        process.kill()
        return {"error": f"Agent timed out after {timeout}s"}
