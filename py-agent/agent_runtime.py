import sys
import json


def handle_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "ping":
        return {"pong": True, "agent": "cococat-mvp"}
    elif method == "echo":
        return params
    else:
        return {"error": f"unknown method: {method}"}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        request = json.loads(line)
        req_id = request.get("id")

        try:
            result = handle_request(request)
            response = {"jsonrpc": "2.0", "result": result, "id": req_id}
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -1, "message": str(e)},
                "id": req_id,
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
