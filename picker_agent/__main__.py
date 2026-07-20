from __future__ import annotations

import argparse
import asyncio

from .connection import AgentConnection


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Workflow Builder element picker agent")
    parser.add_argument("--server", default="ws://127.0.0.1:8000")
    parser.add_argument("--token", help="Legacy one-time token; normally omit this and use automatic pairing")
    parser.add_argument("--pairing-code", help="Optional pairing code override for testing")
    args = parser.parse_args()
    asyncio.run(AgentConnection(args.server, args.token, args.pairing_code).run())


if __name__ == "__main__":
    main()
