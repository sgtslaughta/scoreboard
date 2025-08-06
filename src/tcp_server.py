"""
TCP server for CTF scoreboard submissions.
"""

import asyncio
from typing import Any
from .web_handlers import WebHandlers


class TCPServer:
    """Handles TCP socket connections and score submissions."""

    def __init__(
        self,
        db_manager: Any,
        config: Any,
    ) -> None:
        self.db = db_manager
        self.config = config

        # Welcome message for TCP clients (configurable based on solution requirements)
        if self.config.get("submission", "require_solutions"):
            format_msg = "name,challenge,score,solve_code"
        else:
            format_msg = "name,challenge,score[,solve_code]"

        ctf_name = self.config.get("ctf_name")
        welcome_text = f"Welcome to {ctf_name}! Please submit your credentials in format: {format_msg}\n"
        self.welcome_msg = welcome_text.encode("ascii")

    async def get_scoreboard_response(
        self,
        lab_number: str,
    ) -> str:
        """
        Generate scoreboard response for a specific lab (compatibility method).

        @param lab_number: Challenge/lab identifier to get scoreboard for
        @return: Formatted string containing the scoreboard
        """
        leaderboard_data = await self.db.get_challenge_leaderboard(lab_number, 10)

        if not leaderboard_data:
            return f"Lab {lab_number} Scoreboard:\nNo entries yet!\n"

        response = f"Lab {lab_number} Scoreboard:\n"
        response += "=" * 30 + "\n"

        web_handler = WebHandlers(self.db, self.config)
        ranked_leaderboard = web_handler.calculate_ranks_with_ties(leaderboard_data)

        for entry in ranked_leaderboard:
            timestamp_str = entry["timestamp"][:19] if entry["timestamp"] else "Unknown"
            tie_indicator = " (tie)" if entry["is_tied"] else ""
            rank = entry["rank"]
            player = entry["player"]
            score = entry["score"]
            response += (
                f"{rank:2d}. {player:<15} "
                f"Score: {score:4d} ({timestamp_str}){tie_indicator}\n"
            )

        if len(leaderboard_data) == 10:
            # Check if there are more entries
            all_entries = await self.db.get_challenge_leaderboard(lab_number, 1000)
            if len(all_entries) > 10:
                response += f"... and {len(all_entries) - 10} more entries\n"

        return response

    async def handle_socket_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle individual TCP client connection (async).

        Processes score submissions from TCP clients, validates data,
        and returns formatted scoreboard responses.

        @param reader: AsyncIO stream reader for client connection
        @param writer: AsyncIO stream writer for client connection
        """
        client_addr = writer.get_extra_info("peername")
        print(f"Socket client connected: {client_addr}")

        try:
            # Send welcome message
            writer.write(self.welcome_msg)
            await writer.drain()

            # Receive client data (read until newline or up to 1024 bytes)
            data = await reader.read(1024)
            if not data:
                print(f"No data received from {client_addr}")
                return

            # Parse client message: "name,challenge,score[,solve_code]"
            try:
                message = data.decode("ascii").strip("\x00").strip()
                parts = message.split(
                    ",", 3
                )  # Split into max 4 parts to allow commas in solve code

                require_solutions = self.config.get("submission", "require_solutions")

                if require_solutions and len(parts) != 4:
                    response = "Error: Invalid message format. Expected: name,challenge,score,solve_code\n"
                elif not require_solutions and len(parts) < 3:
                    response = "Error: Invalid message format. Expected: name,challenge,score[,solve_code]\n"
                elif not require_solutions and len(parts) > 4:
                    response = "Error: Too many fields in message\n"
                else:
                    name = parts[0].strip()
                    lab_number = parts[1].strip()
                    score_str = parts[2].strip()
                    solve_code = (
                        parts[3].strip() if len(parts) > 3 else "No solution provided"
                    )

                    # Validate inputs according to protocol specs
                    if not name:
                        response = "Error: Name cannot be empty\n"
                    elif len(name) > 30:
                        response = "Error: Name too long (max 30 characters)\n"
                    elif not lab_number:
                        response = "Error: Lab number cannot be empty\n"
                    elif require_solutions and not solve_code:
                        response = "Error: Solve code cannot be empty\n"
                    else:
                        try:
                            score = int(score_str)
                            if score < 0:
                                response = "Error: Score must be non-negative\n"
                            else:
                                # Add to scoreboard
                                client_ip = client_addr[0] if client_addr else ""
                                await self.db.save_score(
                                    name, lab_number, score, solve_code, client_ip
                                )
                                # Generate formatted scoreboard response
                                response = await self.get_scoreboard_response(
                                    lab_number
                                )
                        except ValueError:
                            response = "Error: Score must be a valid integer\n"

            except UnicodeDecodeError:
                response = "Error: Invalid character encoding\n"

            # Send response
            response_bytes = response.encode("ascii")
            writer.write(response_bytes)
            await writer.drain()

        except (ConnectionError, OSError, UnicodeDecodeError) as e:
            print(f"Error handling socket client {client_addr}: {e}")
            try:
                error_msg = "Server error occurred\n"
                writer.write(error_msg.encode("ascii"))
                await writer.drain()
            except (ConnectionError, OSError):
                pass

        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            print(f"Socket client disconnected: {client_addr}")

    async def start_tcp_server(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> asyncio.AbstractServer:
        """
        Start the TCP socket server.

        @param host: Host address to bind the server to (default "0.0.0.0")
        @param port: Port number to listen on (default 8080)
        @return: TCP server instance
        """
        server = await asyncio.start_server(self.handle_socket_client, host, port)
        print(f"Socket server running on {host}:{port}")

        return server
