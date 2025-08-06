#!/usr/bin/env python3
"""
Async Scoreboard server that implements the protocol expected by the client.
Maintains a persistent scoreboard and handles multiple client connections.
Features both TCP socket server and web interface.
"""

import argparse
import asyncio
import os
from pathlib import Path

from src.scoreboard import ScoreboardSystem


async def main():
    """Main function with command line interface."""

    parser = argparse.ArgumentParser(
        description="CTF Scoreboard Server with TCP socket and web interfaces",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--socket-port", 
        type=int, 
        default=int(os.getenv("SOCKET_PORT", "8080")), 
        help="TCP socket server port (env: SOCKET_PORT)"
    )
    parser.add_argument(
        "--web-port", 
        type=int, 
        default=int(os.getenv("WEB_PORT", "8081")), 
        help="Web interface port (env: WEB_PORT)"
    )
    parser.add_argument(
        "--db", 
        default=os.getenv("DB_PATH", "scoreboard.db"), 
        help="SQLite database file path (env: DB_PATH)"
    )
    parser.add_argument(
        "--config", 
        default=os.getenv("CONFIG_PATH", "ctf_config.json"), 
        help="Configuration file path (env: CONFIG_PATH)"
    )
    parser.add_argument(
        "--host", 
        default=os.getenv("HOST", "0.0.0.0"), 
        help="Host to bind servers to (env: HOST)"
    )

    args = parser.parse_args()

    config_path = Path(args.config)

    if config_path.exists() and not config_path.is_file():
        print(f"Error: {args.config} exists but is not a file")
        return

    system = ScoreboardSystem(
        host=args.host,
        port=args.socket_port,
        web_port=args.web_port,
        db_path=args.db,
        config_path=args.config,
    )

    await system.init_db()
    await system.print_full_scoreboard()

    try:
        await system.run_both_servers()
    except KeyboardInterrupt:
        print("\nServer interrupted")


if __name__ == "__main__":
    asyncio.run(main())
