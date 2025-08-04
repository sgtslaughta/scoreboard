#!/usr/bin/env python3
"""
Async Scoreboard server that implements the protocol expected by the client.
Maintains a persistent scoreboard and handles multiple client connections.
Features both TCP socket server and web interface.
"""

import asyncio
import sys
import time
from datetime import datetime

import aiosqlite
from aiohttp import web, web_runner
import aiohttp_cors
from jinja2 import Environment, FileSystemLoader


class ScoreboardSystem:
    """Async scoreboard system with TCP and web interfaces."""

    def __init__(
        self, host="0.0.0.0", port=8080, db_path="scoreboard.db", web_port=8081
    ):
        self.host = host
        self.port = port
        self.web_port = web_port
        self.db_path = db_path
        self.running = False
        self._db_pool = None

        # Simple in-memory cache with TTL
        self._cache = {}
        self._cache_ttl = 30  # 30 seconds TTL

        # Welcome message for TCP clients
        welcome_text = "Welcome to the CTF Scoreboard! Please submit your credentials in format: name,challenge,score,solve_code\n"
        self.welcome_msg = welcome_text.encode("ascii")

        # Setup Jinja2 templating with caching enabled
        self.jinja_env = Environment(
            loader=FileSystemLoader("templates"),
            auto_reload=False,  # Disable auto-reload for performance
            cache_size=50,  # Cache up to 50 templates
        )

    def _get_cache_key(self, *args):
        """Generate a cache key from arguments."""
        return ":".join(str(arg) for arg in args)

    def _get_from_cache(self, cache_key):
        """Get value from cache if valid."""
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return data
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        return None

    def _set_cache(self, cache_key, data):
        """Set value in cache with current timestamp."""
        self._cache[cache_key] = (data, time.time())

    def _invalidate_cache(self, pattern=None):
        """Invalidate cache entries matching pattern or all if None."""
        if pattern is None:
            self._cache.clear()
        else:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]

    async def get_db_connection(self):
        """Get a database connection from the pool or create a new one."""
        # For now, create individual connections (full pooling would require additional deps)
        # This is still better than the original because we'll optimize query patterns
        return aiosqlite.connect(self.db_path)

    async def execute_db_query(self, query, params=None):
        """Execute a database query with connection management."""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for better concurrent access
            await db.execute("PRAGMA journal_mode=WAL")
            cursor = await db.execute(query, params or ())
            return await cursor.fetchall()

    async def execute_db_write(self, query, params=None):
        """Execute a database write operation with connection management."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(query, params or ())
            await db.commit()
            return db.lastrowid

    async def batch_db_operations(self, operations):
        """Execute multiple database operations concurrently when possible."""
        # For read operations, we can run them concurrently
        read_ops = [op for op in operations if op.get("type") == "read"]
        write_ops = [op for op in operations if op.get("type") == "write"]

        results = {}

        # Execute read operations concurrently
        if read_ops:
            read_tasks = []
            for op in read_ops:
                task = self.execute_db_query(op["query"], op.get("params"))
                read_tasks.append(task)

            read_results = await asyncio.gather(*read_tasks)
            for i, op in enumerate(read_ops):
                results[op.get("key", i)] = read_results[i]

        # Execute write operations sequentially (SQLite limitation)
        for op in write_ops:
            result = await self.execute_db_write(op["query"], op.get("params"))
            results[op.get("key", len(results))] = result

        return results

    async def init_db(self):
        """Initialize the SQLite database with optimized schema and indexes."""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for better concurrent access
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")  # Better performance
            await db.execute("PRAGMA cache_size=10000")  # 10MB cache
            await db.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp storage

            await db.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    challenge TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    solve_code TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    client_ip TEXT
                )
            """)

            # Optimized indexes for performance
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_challenge_score_timestamp 
                ON scores(challenge, score ASC, timestamp ASC)
            """)
            await db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_player_challenge 
                ON scores(player_name, challenge)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON scores(timestamp DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_challenge_only 
                ON scores(challenge)
            """)

            await db.commit()

            # Handle schema migration for solve_code column
            await self._migrate_schema(db)

    async def _migrate_schema(self, db):
        """Handle database schema migrations."""
        # Check if solve_code column exists
        cursor = await db.execute("PRAGMA table_info(scores)")
        columns = await cursor.fetchall()
        column_names = [column[1] for column in columns]

        if "solve_code" not in column_names:
            print("Migrating database schema to add solve_code column...")
            await db.execute(
                "ALTER TABLE scores ADD COLUMN solve_code TEXT DEFAULT 'No solution provided'"
            )
            await db.commit()
            print("Schema migration completed.")

    async def save_score(self, player_name, challenge, score, solve_code, client_ip=""):
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
                        "UPDATE scores SET score = ?, solve_code = ?, timestamp = CURRENT_TIMESTAMP, "
                        "client_ip = ? WHERE player_name = ? AND challenge = ?",
                        (score, solve_code, client_ip, player_name, challenge),
                    )
                    print(
                        f"Updated score for {player_name} in {challenge}: "
                        f"{old_score} -> {score}"
                    )
                    await db.commit()
                    # Invalidate cache when score is updated
                    self._invalidate_cache()
                    return True

                print(
                    f"Score {score} for {player_name} in {challenge} "
                    f"not better than existing {old_score}"
                )
                return False

            await db.execute(
                "INSERT INTO scores (player_name, challenge, score, solve_code, client_ip) "
                "VALUES (?, ?, ?, ?, ?)",
                (player_name, challenge, score, solve_code, client_ip),
            )
            print(f"Added new entry: {player_name} in {challenge} with score {score}")
            await db.commit()
            # Invalidate cache when new score is added
            self._invalidate_cache()
            return True

    async def get_challenge_leaderboard(self, challenge, limit=10):
        """Get leaderboard for a specific challenge."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT player_name, score, timestamp, solve_code 
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

    async def get_all_challenge_data_optimized(self):
        """Get all challenge data in a single optimized query for web index."""
        # Check cache first
        cache_key = self._get_cache_key("all_challenge_data")
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            return cached_data

        async with aiosqlite.connect(self.db_path) as db:
            # Get all challenges with their top 5 players in one query
            cursor = await db.execute("""
                WITH RankedScores AS (
                    SELECT 
                        challenge,
                        player_name,
                        score,
                        timestamp,
                        solve_code,
                        ROW_NUMBER() OVER (PARTITION BY challenge ORDER BY score ASC, timestamp ASC) as rank
                    FROM scores
                ),
                TopPlayers AS (
                    SELECT 
                        challenge,
                        player_name,
                        score,
                        timestamp,
                        solve_code,
                        rank
                    FROM RankedScores
                    WHERE rank <= 5
                ),
                ChallengeLeaders AS (
                    SELECT 
                        challenge,
                        player_name as leader_name,
                        score as leader_score
                    FROM RankedScores
                    WHERE rank = 1
                )
                SELECT 
                    tp.challenge,
                    tp.player_name,
                    tp.score,
                    tp.timestamp,
                    tp.solve_code,
                    tp.rank,
                    cl.leader_name,
                    cl.leader_score
                FROM TopPlayers tp
                LEFT JOIN ChallengeLeaders cl ON tp.challenge = cl.challenge
                ORDER BY tp.challenge, tp.rank
            """)
            results = await cursor.fetchall()

            # Transform results into structured data
            challenges_data = {}
            for row in results:
                (
                    challenge,
                    player,
                    score,
                    timestamp,
                    solve_code,
                    rank,
                    leader_name,
                    leader_score,
                ) = row

                if challenge not in challenges_data:
                    challenges_data[challenge] = {
                        "name": challenge,
                        "leader": {"name": leader_name, "score": leader_score}
                        if leader_name
                        else None,
                        "top5": [],
                    }

                # Add to top5 list
                challenges_data[challenge]["top5"].append(
                    {
                        "rank": rank,
                        "player": player,
                        "score": score,
                        "timestamp": timestamp,
                        "solve_code": solve_code,
                        "is_tied": False,  # Will calculate ties later
                    }
                )

            # Calculate ties for each challenge
            for challenge_data in challenges_data.values():
                top5 = challenge_data["top5"]
                if len(top5) > 1:
                    for i, entry in enumerate(top5):
                        # Check if tied with previous or next entry
                        is_tied = False
                        if i > 0 and top5[i - 1]["score"] == entry["score"]:
                            is_tied = True
                        if i < len(top5) - 1 and top5[i + 1]["score"] == entry["score"]:
                            is_tied = True
                        entry["is_tied"] = is_tied

            result = list(challenges_data.values())
            # Cache the result
            self._set_cache(cache_key, result)
            return result

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
            response += (
                f"{entry['rank']:2d}. {entry['player']:<15} "
                f"Score: {entry['score']:4d} ({timestamp_str}){tie_indicator}\n"
            )

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
            # Send welcome message
            writer.write(self.welcome_msg)
            await writer.drain()

            # Receive client data (read until newline or up to 1024 bytes)
            data = await reader.read(1024)
            if not data:
                print(f"No data received from {client_addr}")
                return

            # Parse client message: "name,challenge,score,solve_code"
            try:
                message = data.decode("ascii").strip("\x00").strip()
                parts = message.split(
                    ",", 3
                )  # Split into max 4 parts to allow commas in solve code

                if len(parts) != 4:
                    response = "Error: Invalid message format. Expected: name,challenge,score,solve_code\n"
                else:
                    name = parts[0].strip()
                    lab_number = parts[1].strip()
                    score_str = parts[2].strip()
                    solve_code = parts[3].strip()

                    # Validate inputs according to protocol specs
                    if not name:
                        response = "Error: Name cannot be empty\n"
                    elif len(name) > 30:
                        response = "Error: Name too long (max 30 characters)\n"
                    elif not lab_number:
                        response = "Error: Lab number cannot be empty\n"
                    elif not solve_code:
                        response = "Error: Solve code cannot be empty\n"
                    else:
                        try:
                            score = int(score_str)
                            if score < 0:
                                response = "Error: Score must be non-negative\n"
                            else:
                                # Add to scoreboard
                                client_ip = client_addr[0] if client_addr else ""
                                await self.save_score(
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

    # Web Server Methods
    async def web_index(self, _request):
        """Web interface main page."""
        # Use optimized single-query method to get all challenge data
        challenges_data = await self.get_all_challenge_data_optimized()

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

        for i, entry in enumerate(leaderboard_data):
            if len(entry) == 4:  # New format with solve_code
                player, score, timestamp, solve_code = entry
            else:  # Old format without solve_code
                player, score, timestamp = entry
                solve_code = "No solution provided"
            # If this score is different from previous, update rank to current position
            if previous_score is not None and score != previous_score:
                current_rank = i + 1

            # Determine rank class for styling
            rank_class = ""
            is_tied = False

            # Check if this player is tied with others
            if i > 0 and leaderboard_data[i - 1][1] == score:
                is_tied = True
            elif i < len(leaderboard_data) - 1 and leaderboard_data[i + 1][1] == score:
                is_tied = True

            # Set rank class based on actual rank position
            if current_rank == 1:
                rank_class = "gold"
            elif current_rank == 2:
                rank_class = "silver"
            elif current_rank == 3:
                rank_class = "bronze"

            ranked_data.append(
                {
                    "rank": current_rank,
                    "rank_class": rank_class,
                    "player": player,
                    "score": score,
                    "timestamp": timestamp,
                    "solve_code": solve_code,
                    "is_tied": is_tied,
                }
            )

            previous_score = score

        return ranked_data

    async def get_player_rankings(self):
        """Get overall player rankings based on total scores across all challenges."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT 
                    player_name,
                    COUNT(*) as challenges_solved,
                    SUM(score) as total_score,
                    AVG(score) as avg_score,
                    MIN(score) as best_score,
                    MAX(timestamp) as last_activity
                FROM scores 
                GROUP BY player_name 
                ORDER BY challenges_solved DESC, total_score ASC, avg_score ASC
            """)
            results = await cursor.fetchall()

            # Add ranking
            ranked_players = []
            for rank, (
                player,
                challenges,
                total,
                avg,
                best,
                last_activity,
            ) in enumerate(results, 1):
                ranked_players.append(
                    {
                        "rank": rank,
                        "player": player,
                        "challenges_solved": challenges,
                        "total_score": total,
                        "avg_score": round(avg, 1),
                        "best_score": best,
                        "last_activity": last_activity,
                    }
                )

            return ranked_players

    async def get_player_details(self, player_name):
        """Get detailed information about a specific player's solutions."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT challenge, score, solve_code, timestamp
                FROM scores 
                WHERE player_name = ?
                ORDER BY score ASC, timestamp DESC
            """,
                (player_name,),
            )
            return await cursor.fetchall()

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
            except (ValueError, TypeError):
                formatted_date = (
                    entry["timestamp"][:19] if entry["timestamp"] else "Unknown"
                )

            leaderboard.append(
                {
                    "rank": entry["rank"],
                    "rank_class": entry["rank_class"],
                    "player": entry["player"],
                    "score": entry["score"],
                    "formatted_date": formatted_date,
                    "solve_code": entry["solve_code"],
                    "is_tied": entry["is_tied"],
                }
            )

        template = self.jinja_env.get_template("challenge_detail.html")
        html = template.render(
            title=challenge_name, challenge_name=challenge_name, leaderboard=leaderboard
        )
        return web.Response(text=html, content_type="text/html")

    async def web_player_rankings(self, _request):
        """Web interface player rankings page."""
        player_rankings = await self.get_player_rankings()

        template = self.jinja_env.get_template("player_rankings.html")
        html = template.render(title="Player Rankings", players=player_rankings)
        return web.Response(text=html, content_type="text/html")

    async def web_player_details(self, request):
        """Web interface player details page."""
        player_name = request.match_info["player"]
        player_details = await self.get_player_details(player_name)

        # Format details for display
        challenges = []
        for challenge, score, solve_code, timestamp in player_details:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_date = timestamp[:19] if timestamp else "Unknown"

            challenges.append(
                {
                    "challenge": challenge,
                    "score": score,
                    "solve_code": solve_code,
                    "formatted_date": formatted_date,
                }
            )

        template = self.jinja_env.get_template("player_details.html")
        html = template.render(
            title=f"Player: {player_name}",
            player_name=player_name,
            challenges=challenges,
        )
        return web.Response(text=html, content_type="text/html")

    async def web_api_challenges(self, _request):
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

        # Static files route
        app.router.add_static("/static/", path="static", name="static")

        # Web routes
        app.router.add_get("/", self.web_index)
        app.router.add_get("/challenge/{challenge}", self.web_challenge_detail)
        app.router.add_get("/players", self.web_player_rankings)
        app.router.add_get("/player/{player}", self.web_player_details)

        # API routes
        app.router.add_get("/api/challenges", self.web_api_challenges)
        app.router.add_get("/api/leaderboard/{challenge}", self.web_api_leaderboard)

        # Add CORS to all routes
        for route in list(app.router.routes()):
            cors.add(route)

        app_runner = web_runner.AppRunner(app)
        await app_runner.setup()
        site = web_runner.TCPSite(app_runner, host, port)
        await site.start()
        print(f"Web server running on http://{host}:{port}")
        return app_runner

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

    async def print_full_scoreboard(self):
        """Print the complete scoreboard to console with optimized queries."""
        print("\n" + "=" * 50)
        print("COMPLETE SCOREBOARD")
        print("=" * 50)

        # Single query to get all data at once
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            cursor = await db.execute("""
                SELECT challenge, player_name, score, timestamp, client_ip
                FROM scores 
                ORDER BY challenge, score ASC, timestamp ASC
            """)
            all_scores = await cursor.fetchall()

        if not all_scores:
            print("Scoreboard is empty")
            return

        current_challenge = None
        position = 0

        for challenge, player, score, timestamp, client_ip in all_scores:
            if challenge != current_challenge:
                current_challenge = challenge
                position = 0
                print(f"\nLab {challenge}:")
                print("-" * 20)

            position += 1
            timestamp_str = timestamp[:19] if timestamp else "Unknown"
            client_ip_str = client_ip if client_ip else "Unknown"

            print(
                f"{position:2d}. {player:<15} Score: {score:4d} "
                f"({timestamp_str}) [{client_ip_str}]"
            )


async def main():
    """Main function with command line interface."""

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
