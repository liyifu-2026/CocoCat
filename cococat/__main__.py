"""CocoCat v2 server entry point.

Usage:
    python -m cococat                              # local mode (port 8000)
    python -m cococat --port 8000 --cube-sandbox   # CubeSandbox MicroVM mode
"""
from __future__ import annotations

import argparse
import logging
import os
import uvicorn

from cococat.app import create_app

logger = logging.getLogger("cococat")


def main():
    parser = argparse.ArgumentParser(description="CocoCat v2 server")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    parser.add_argument("--db", type=str, default="cococat.db", help="SQLite database path")
    parser.add_argument("--auth", type=str, default="config/auth.json", help="Auth config path")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--log-level", type=str, default="info", help="Log level")
    parser.add_argument("--cube-sandbox", action="store_true",
                        help="Enable CubeSandbox MicroVM for code execution (bash tool)")
    parser.add_argument("--cube-sandbox-template", type=str,
                        default=os.environ.get("CUBESANDBOX_TEMPLATE_ID", "tpl-dedcd9373c3f49939f7feb9b"),
                        help="CubeSandbox template ID")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = create_app(args.db)

    from cococat.core.bootstrap import load_agents
    load_agents(app, args)

    logger.info("Starting CocoCat v2 on http://%s:%d (cube_sandbox=%s)", args.host, args.port, args.cube_sandbox)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()
