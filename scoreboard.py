#!/usr/bin/env python3
"""
Async Scoreboard server that implements the protocol expected by the client.
Maintains a persistent scoreboard and handles multiple client connections.
Features both TCP socket server and web interface.
"""

import asyncio
import aiosqlite
import json
import os
from datetime import datetime
from aiohttp import web, web_runner
import aiohttp_cors
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader


class ScoreboardSystem:
    def __init__(
        self, host="0.0.0.0", port=8080, db_path="scoreboard.db", web_port=8081
    ):
        self.host = host
        self.port = port
        self.web_port = web_port
        self.db_path = db_path
        self.running = False

        # Initial challenge/welcome message (sent first to client) - exactly 512 bytes
        welcome_text = "Welcome to the CTF Scoreboard! Please submit your credentials."
        self.welcome_msg = welcome_text.encode("ascii").ljust(512, b"\x00")

        # Setup Jinja2 templating
        self.jinja_env = Environment(loader=FileSystemLoader("templates"))

    async def init_db(self):
        """Initialize the SQLite database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    challenge TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    client_ip TEXT
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_challenge_score 
                ON scores(challenge, score ASC)
            """)
            await db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_player_challenge 
                ON scores(player_name, challenge)
            """)
            await db.commit()

    async def save_score(self, player_name, challenge, score, client_ip=""):
        """Save a score to the database, updating if better score exists."""
        async with aiosqlite.connect(self.db_path) as db:
            # Check for existing score
            cursor = await db.execute(
                "SELECT score FROM scores WHERE player_name = ? AND challenge = ?",
                (player_name, challenge),
            )
            existing = await cursor.fetchone()

            if existing:
                old_score = existing[0]
                if score < old_score:  # Lower score is better
                    await db.execute(
                        "UPDATE scores SET score = ?, timestamp = CURRENT_TIMESTAMP, client_ip = ? WHERE player_name = ? AND challenge = ?",
                        (score, client_ip, player_name, challenge),
                    )
                    print(
                        f"Updated score for {player_name} in {challenge}: {old_score} -> {score}"
                    )
                    await db.commit()
                    return True
                else:
                    print(
                        f"Score {score} for {player_name} in {challenge} not better than existing {old_score}"
                    )
                    return False
            else:
                await db.execute(
                    "INSERT INTO scores (player_name, challenge, score, client_ip) VALUES (?, ?, ?, ?)",
                    (player_name, challenge, score, client_ip),
                )
                print(
                    f"Added new entry: {player_name} in {challenge} with score {score}"
                )
                await db.commit()
                return True

    async def get_challenge_leaderboard(self, challenge, limit=10):
        """Get leaderboard for a specific challenge."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT player_name, score, timestamp 
                FROM scores 
                WHERE challenge = ? 
                ORDER BY score ASC 
                LIMIT ?
            """,
                (challenge, limit),
            )
            return await cursor.fetchall()

    async def get_all_challenges(self):
        """Get all available challenges."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT DISTINCT challenge FROM scores ORDER BY challenge"
            )
            return [row[0] for row in await cursor.fetchall()]

    async def get_top_player_per_challenge(self):
        """Get top player for each challenge."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT challenge, player_name, MIN(score) as top_score
                FROM scores 
                GROUP BY challenge
                ORDER BY challenge
            """)
            return await cursor.fetchall()

    async def get_scoreboard_response(self, lab_number):
        """Generate scoreboard response for a specific lab (compatibility method)."""
        leaderboard_data = await self.get_challenge_leaderboard(lab_number, 10)

        if not leaderboard_data:
            return f"Lab {lab_number} Scoreboard:\nNo entries yet!\n"

        response = f"Lab {lab_number} Scoreboard:\n"
        response += "=" * 30 + "\n"

        # Calculate ranks with ties
        ranked_leaderboard = self.calculate_ranks_with_ties(leaderboard_data)
        
        for entry in ranked_leaderboard:
            timestamp_str = entry["timestamp"][:19] if entry["timestamp"] else "Unknown"
            tie_indicator = " (tie)" if entry["is_tied"] else ""
            response += f"{entry['rank']:2d}. {entry['player']:<15} Score: {entry['score']:4d} ({timestamp_str}){tie_indicator}\n"

        if len(leaderboard_data) == 10:
            # Check if there are more entries
            all_entries = await self.get_challenge_leaderboard(lab_number, 1000)
            if len(all_entries) > 10:
                response += f"... and {len(all_entries) - 10} more entries\n"

        return response

    async def handle_socket_client(self, reader, writer):
        """Handle individual TCP client connection (async)."""
        client_addr = writer.get_extra_info("peername")
        print(f"Socket client connected: {client_addr}")

        try:
            # Send welcome message first (exactly 512 bytes as expected by client)
            writer.write(self.welcome_msg)
            await writer.drain()

            # Receive client data (read exactly 512 bytes as per protocol)
            data = await reader.read(512)
            if not data:
                print(f"No data received from {client_addr}")
                return

            # Parse client message: "name,lab_number,score"
            try:
                message = data.decode("ascii").strip("\x00").strip()
                parts = message.split(",")

                if len(parts) != 3:
                    response = "Error: Invalid message format. Expected: name,lab_number,score\n"
                else:
                    name = parts[0].strip()
                    lab_number = parts[1].strip()
                    score_str = parts[2].strip()

                    # Validate inputs according to protocol specs
                    if not name:
                        response = "Error: Name cannot be empty\n"
                    elif len(name) > 30:
                        response = "Error: Name too long (max 30 characters)\n"
                    elif not lab_number:
                        response = "Error: Lab number cannot be empty\n"
                    elif len(lab_number) > 4:
                        response = "Error: Lab number too long (max 4 characters)\n"
                    else:
                        try:
                            score = int(score_str)
                            if score < 0:
                                response = "Error: Score must be non-negative\n"
                            else:
                                # Add to scoreboard
                                client_ip = client_addr[0] if client_addr else ""
                                await self.save_score(
                                    name, lab_number, score, client_ip
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

        except Exception as e:
            print(f"Error handling socket client {client_addr}: {e}")
            try:
                error_msg = "Server error occurred\n"
                writer.write(error_msg.encode("ascii"))
                await writer.drain()
            except:
                pass

        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            print(f"Socket client disconnected: {client_addr}")

    # Web Server Methods
    async def web_index(self, request):
        """Web interface main page."""
        challenge_names = await self.get_all_challenges()
        leaders = await self.get_top_player_per_challenge()

        # Prepare challenge data with enriched information
        challenges_data = []
        for challenge_name in challenge_names:
            leaderboard = await self.get_challenge_leaderboard(challenge_name, 5)
            leader_info = next((l for l in leaders if l[0] == challenge_name), None)

            challenge_data = {"name": challenge_name, "leader": None, "top5": []}

            if leader_info:
                challenge_data["leader"] = {
                    "name": leader_info[1],
                    "score": leader_info[2],
                }

            if leaderboard:
                # Calculate ranks with ties for top 5
                top5_ranked = self.calculate_ranks_with_ties(leaderboard[:5])
                for entry in top5_ranked:
                    challenge_data["top5"].append({
                        "rank": entry["rank"],
                        "player": entry["player"],
                        "score": entry["score"],
                        "is_tied": entry["is_tied"]
                    })

            challenges_data.append(challenge_data)

        template = self.jinja_env.get_template("index.html")
        html = template.render(title="Home", challenges=challenges_data)
        return web.Response(text=html, content_type="text/html")

    def calculate_ranks_with_ties(self, leaderboard_data):
        """Calculate ranks accounting for ties (same scores get same rank)."""
        if not leaderboard_data:
            return []
        
        ranked_data = []
        current_rank = 1
        previous_score = None
        
        for i, (player, score, timestamp) in enumerate(leaderboard_data):
            # If this score is different from previous, update rank to current position
            if previous_score is not None and score != previous_score:
                current_rank = i + 1
            
            # Determine rank class for styling
            rank_class = ""
            is_tied = False
            
            # Check if this player is tied with others
            if i > 0 and leaderboard_data[i-1][1] == score:
                is_tied = True
            elif i < len(leaderboard_data) - 1 and leaderboard_data[i+1][1] == score:
                is_tied = True
            
            # Set rank class based on actual rank position
            if current_rank == 1:
                rank_class = "gold"
            elif current_rank == 2:
                rank_class = "silver"
            elif current_rank == 3:
                rank_class = "bronze"
            
            ranked_data.append({
                "rank": current_rank,
                "rank_class": rank_class,
                "player": player,
                "score": score,
                "timestamp": timestamp,
                "is_tied": is_tied
            })
            
            previous_score = score
        
        return ranked_data

    async def web_challenge_detail(self, request):
        """Web interface challenge detail page."""
        challenge_name = request.match_info["challenge"]
        leaderboard_data = await self.get_challenge_leaderboard(challenge_name, 50)

        # Calculate ranks with tie support
        ranked_leaderboard = self.calculate_ranks_with_ties(leaderboard_data)
        
        # Format timestamps
        leaderboard = []
        for entry in ranked_leaderboard:
            try:
                dt = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_date = entry["timestamp"][:19] if entry["timestamp"] else "Unknown"
            
            leaderboard.append({
                "rank": entry["rank"],
                "rank_class": entry["rank_class"],
                "player": entry["player"],
                "score": entry["score"],
                "formatted_date": formatted_date,
                "is_tied": entry["is_tied"]
            })

        template = self.jinja_env.get_template("challenge_detail.html")
        html = template.render(
            title=challenge_name, challenge_name=challenge_name, leaderboard=leaderboard
        )
        return web.Response(text=html, content_type="text/html")

    async def web_api_challenges(self, request):
        """API endpoint for challenges."""
        challenges = await self.get_all_challenges()
        return web.json_response({"challenges": challenges})

    async def web_api_leaderboard(self, request):
        """API endpoint for leaderboard."""
        challenge = request.match_info["challenge"]
        limit = int(request.query.get("limit", 10))
        leaderboard = await self.get_challenge_leaderboard(challenge, limit)

        return web.json_response(
            {
                "challenge": challenge,
                "leaderboard": [
                    {
                        "rank": i + 1,
                        "player": row[0],
                        "score": row[1],
                        "timestamp": row[2],
                    }
                    for i, row in enumerate(leaderboard)
                ],
            }
        )

    async def start_web_server(self, host="localhost", port=None):
        """Start the web server."""
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

        # Web routes
        app.router.add_get("/", self.web_index)
        app.router.add_get("/challenge/{challenge}", self.web_challenge_detail)

        # API routes
        app.router.add_get("/api/challenges", self.web_api_challenges)
        app.router.add_get("/api/leaderboard/{challenge}", self.web_api_leaderboard)

        # Add CORS to all routes
        for route in list(app.router.routes()):
            cors.add(route)

        runner = web_runner.AppRunner(app)
        await runner.setup()
        site = web_runner.TCPSite(runner, host, port)
        await site.start()
        print(f"Web server running on http://{host}:{port}")
        return runner

    async def start_socket_server(self, host=None, port=None):
        """Start the TCP socket server."""
        if host is None:
            host = self.host
        if port is None:
            port = self.port

        server = await asyncio.start_server(self.handle_socket_client, host, port)
        print(f"Socket server running on {host}:{port}")
        return server

    async def run_both_servers(
        self, socket_host=None, socket_port=None, web_host="localhost", web_port=None
    ):
        """Run both TCP socket server and web server."""
        if socket_host is None:
            socket_host = self.host
        if socket_port is None:
            socket_port = self.port
        if web_port is None:
            web_port = self.web_port

        # Start both servers
        socket_server = await self.start_socket_server(socket_host, socket_port)
        web_runner = await self.start_web_server(web_host, web_port)

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
            await web_runner.cleanup()

    async def print_full_scoreboard(self):
        """Print the complete scoreboard to console."""
        challenges = await self.get_all_challenges()

        if not challenges:
            print("Scoreboard is empty")
            return

        print("\n" + "=" * 50)
        print("COMPLETE SCOREBOARD")
        print("=" * 50)

        for challenge in sorted(challenges):
            print(f"\nLab {challenge}:")
            print("-" * 20)
            leaderboard = await self.get_challenge_leaderboard(
                challenge, 1000
            )  # Get all entries
            for i, (player, score, timestamp) in enumerate(leaderboard, 1):
                timestamp_str = timestamp[:19] if timestamp else "Unknown"
                # Get client IP if available
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(
                        "SELECT client_ip FROM scores WHERE player_name = ? AND challenge = ? AND score = ?",
                        (player, challenge, score),
                    )
                    result = await cursor.fetchone()
                    client_ip = result[0] if result and result[0] else "Unknown"

                print(
                    f"{i:2d}. {player:<15} Score: {score:4d} "
                    f"({timestamp_str}) [{client_ip}]"
                )


async def main():
    """Main function with command line interface."""
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print("Usage: python scoreboard.py [socket_port] [web_port] [db_file]")
            print("Default socket port: 8080")
            print("Default web port: 8081")
            print("Default database file: scoreboard.db")
            return

    # Parse command line arguments
    socket_port = 8080
    web_port = 8081
    db_file = "scoreboard.db"

    if len(sys.argv) > 1:
        try:
            socket_port = int(sys.argv[1])
        except ValueError:
            print("Invalid socket port number")
            return

    if len(sys.argv) > 2:
        try:
            web_port = int(sys.argv[2])
        except ValueError:
            print("Invalid web port number")
            return

    if len(sys.argv) > 3:
        db_file = sys.argv[3]

    # Create server system
    system = ScoreboardSystem(port=socket_port, web_port=web_port, db_path=db_file)

    # Initialize database first
    await system.init_db()

    # Print initial scoreboard
    await system.print_full_scoreboard()

    try:
        await system.run_both_servers()
    except KeyboardInterrupt:
        print("\nServer interrupted")


if __name__ == "__main__":
    asyncio.run(main())
