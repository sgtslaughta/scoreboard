"""
Main ScoreboardSystem class that orchestrates all components.
"""

from typing import Optional
from aiohttp import web, web_runner
import aiohttp_cors

from .config import CTFConfig
from .database import DatabaseManager
from .web_handlers import WebHandlers
from .tcp_server import TCPServer


class ScoreboardSystem:
    """Async scoreboard system with TCP and web interfaces."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        db_path: str = "scoreboard.db",
        web_port: int = 8081,
        config_path: str = "ctf_config.json",
    ) -> None:
        self.host = host
        self.port = port
        self.web_port = web_port
        self.db_path = db_path
        self.running = False

        # Load configuration
        self.config = CTFConfig(config_path)
        # Initialize components
        self.db = DatabaseManager(db_path, self.config)
        self.web_handlers = WebHandlers(self.db, self.config)
        self.tcp_server = TCPServer(self.db, self.config)

    async def init_db(self) -> None:
        """
        Initialize the database.

        Creates database tables and performs any necessary setup.
        """
        await self.db.init_db()

    async def start_web_server(
        self,
        host: str = "localhost",
        port: Optional[int] = None,
    ) -> web_runner.AppRunner:
        """
        Start the web server.

        @param host: Host address to bind the server to (default "localhost")
        @param port: Port number to use (default uses configured web_port)
        @return: AppRunner instance for the web server
        """
        if port is None:
            port = self.web_port

        app = web.Application()

        # Setup CORS
        cors = aiohttp_cors.setup(
            app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*",
                )
            },
        )

        # Static files route
        app.router.add_static("/static/", path="src/static", name="static")

        # Web routes
        app.router.add_get("/", self.web_handlers.web_index)
        app.router.add_get(
            "/challenge/{challenge}", self.web_handlers.web_challenge_detail
        )

        # Conditionally add player ranking routes
        if self.config.is_feature_enabled("player_rankings_enabled"):
            app.router.add_get("/players", self.web_handlers.web_player_rankings)
            app.router.add_get("/player/{player}", self.web_handlers.web_player_details)

        # API routes
        app.router.add_get("/api/challenges", self.web_handlers.web_api_challenges)
        app.router.add_get(
            "/api/leaderboard/{challenge}", self.web_handlers.web_api_leaderboard
        )

        # Add CORS to all routes
        for route in list(app.router.routes()):
            cors.add(route)

        app_runner = web_runner.AppRunner(app)
        await app_runner.setup()

        site = web_runner.TCPSite(app_runner, host, port)
        await site.start()

        print(f"Web server running on http://{host}:{port}")
        return app_runner

    async def start_socket_server(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        """
        Start the TCP socket server.

        @param host: Host address to bind the server to (default uses configured host)
        @param port: Port number to use (default uses configured port)
        @return: TCP server instance
        """
        if host is None:
            host = self.host
        if port is None:
            port = self.port

        return await self.tcp_server.start_tcp_server(host, port)

    async def run_both_servers(
        self,
        socket_host: Optional[str] = None,
        socket_port: Optional[int] = None,
        web_host: str = "localhost",
        web_port: Optional[int] = None,
    ) -> None:
        """
        Run both TCP socket server and web server.

        @param socket_host: TCP server host address (default uses configured host)
        @param socket_port: TCP server port (default uses configured port)
        @param web_host: Web server host address (default "localhost")
        @param web_port: Web server port (default uses configured web_port)
        """
        if socket_host is None:
            socket_host = self.host
        if socket_port is None:
            socket_port = self.port
        if web_port is None:
            web_port = self.web_port

        # Start both servers
        socket_server = await self.start_socket_server(socket_host, socket_port)
        web_server_runner = await self.start_web_server(web_host, web_port)

        print("\nScoreboard System Running!")
        print(f"Socket Server: {socket_host}:{socket_port}")
        print(f"Web Interface: http://{web_host}:{web_port}")
        print("\nPress Ctrl+C to stop...\n")

        try:
            async with socket_server:
                await socket_server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down servers...")
        finally:
            socket_server.close()
            await socket_server.wait_closed()
            await web_server_runner.cleanup()

    async def print_full_scoreboard(self) -> None:
        """
        Print the complete scoreboard to console.

        Delegates to the database manager's print method.
        """
        await self.db.print_full_scoreboard()
