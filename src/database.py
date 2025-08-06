"""
Database operations for CTF scoreboard.
"""

import time
from typing import List, Tuple, Dict, Any, Optional
import aiosqlite


class DatabaseManager:
    """Manages database operations with connection pooling and caching."""

    def __init__(
        self,
        db_path: str,
        config: Any,
    ) -> None:
        self.db_path = db_path
        self.config = config
        # Simple in-memory cache with TTL
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl = 30  # 30 seconds TTL

    def _get_cache_key(self, *args: Any) -> str:
        """
        Generate a cache key from arguments.

        @param args: Variable arguments to create cache key from
        @return: String cache key generated from arguments
        """
        return ":".join(str(arg) for arg in args)

    def _get_from_cache(
        self,
        cache_key: str,
    ) -> Optional[Any]:
        """
        Get value from cache if valid.

        @param cache_key: String cache key to lookup
        @return: Cached data if valid, None if expired or not found
        """
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]

            if time.time() - timestamp < self._cache_ttl:
                return data
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        return None

    def _set_cache(
        self,
        cache_key: str,
        data: Any,
    ) -> None:
        """
        Set value in cache with current timestamp.

        @param cache_key: String cache key to store data under
        @param data: Data to cache
        """
        self._cache[cache_key] = (data, time.time())

    def _invalidate_cache(
        self,
        pattern: Optional[str] = None,
    ) -> None:
        """
        Invalidate cache entries matching pattern or all if None.

        @param pattern: Optional string pattern to match cache keys against
        """
        if pattern is None:
            self._cache.clear()
        else:
            keys_to_remove = [k for k in self._cache if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]

    async def init_db(self) -> None:
        """
        Initialize the SQLite database with optimized schema and indexes.

        Creates tables, indexes, and performs schema migrations if needed.
        """
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

    async def _migrate_schema(
        self,
        db: Any,
    ) -> None:
        """
        Handle database schema migrations.

        @param db: Active database connection
        """
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

    async def save_score(
        self,
        player_name: str,
        challenge: str,
        score: int,
        solve_code: str,
        client_ip: str = "",
    ) -> bool:
        """
        Save a score to the database, updating if better score exists.

        @param player_name: Name of the player
        @param challenge: Challenge name/identifier
        @param score: Numeric score value
        @param solve_code: Solution code provided by player
        @param client_ip: IP address of the client (optional)
        @return: True if score was saved/updated, False if not better than existing
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Check for existing score
            cursor = await db.execute(
                "SELECT score FROM scores WHERE player_name = ? AND challenge = ?",
                (player_name, challenge),
            )
            existing = await cursor.fetchone()

            if existing:
                old_score = existing[0]
                scoring_type = self.config.get("scoring", "scoring_type")

                # Determine if new score is better based on scoring type
                is_better_score = False

                if scoring_type == "golf":
                    is_better_score = score < old_score  # Lower is better for golf
                else:  # standard
                    is_better_score = score > old_score  # Higher is better for standard

                if is_better_score:
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

    async def get_challenge_leaderboard(
        self,
        challenge: str,
        limit: int = 10,
    ) -> List[Any]:
        """
        Get leaderboard for a specific challenge.

        @param challenge: Challenge name to get leaderboard for
        @param limit: Maximum number of entries to return (default 10)
        @return: List of tuples containing player data ordered by score
        """
        # Use configured sort order
        sort_order = self.config.get_sort_order()
        max_entries = self.config.get("ui", "max_leaderboard_entries")
        actual_limit = min(limit, max_entries) if max_entries else limit

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                f"""
                SELECT player_name, score, timestamp, solve_code 
                FROM scores 
                WHERE challenge = ? 
                ORDER BY score {sort_order}, timestamp ASC
                LIMIT ?
            """,
                (challenge, actual_limit),
            )
            rows = await cursor.fetchall()
            return list(rows)

    async def get_all_challenges(self) -> List[str]:
        """
        Get all available challenges.

        @return: List of unique challenge names
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT DISTINCT challenge FROM scores ORDER BY challenge"
            )
            return [row[0] for row in await cursor.fetchall()]

    async def get_top_player_per_challenge(self) -> List[Any]:
        """
        Get top player for each challenge.

        @return: List of tuples containing challenge, player name, and top score
        """
        scoring_type = self.config.get("scoring", "scoring_type")

        if scoring_type == "golf":
            aggregator = "MIN(score)"
        else:  # standard
            aggregator = "MAX(score)"

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"""
                SELECT challenge, player_name, {aggregator} as top_score
                FROM scores 
                GROUP BY challenge
                ORDER BY challenge
            """)
            rows = await cursor.fetchall()

            return list(rows)

    async def get_all_challenge_data_optimized(self) -> List[Dict[str, Any]]:
        """
        Get all challenge data in a single optimized query for web index.

        Uses caching and a single SQL query to efficiently retrieve all
        challenge data with top 5 players for each challenge.

        @return: List of dictionaries containing challenge data with leaderboards
        """
        # Check cache first
        cache_key = self._get_cache_key("all_challenge_data")
        cached_data = self._get_from_cache(cache_key)

        if cached_data is not None:
            return cached_data

        # Use configured sort order
        sort_order = self.config.get_sort_order()

        async with aiosqlite.connect(self.db_path) as db:
            # Get all challenges with their top 5 players in one query
            cursor = await db.execute(f"""
                WITH RankedScores AS (
                    SELECT 
                        challenge,
                        player_name,
                        score,
                        timestamp,
                        solve_code,
                        ROW_NUMBER() OVER (PARTITION BY challenge ORDER BY score {sort_order}, timestamp ASC) as rank
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

    async def get_player_rankings(self) -> List[Dict[str, Any]]:
        """
        Get overall player rankings based on total scores across all challenges.

        @return: List of dictionaries with player ranking information
        """
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

    async def get_player_details(
        self,
        player_name: str,
    ) -> List[Any]:
        """
        Get detailed information about a specific player's solutions.

        @param player_name: Name of the player to get details for
        @return: List of tuples containing challenge details for the player
        """
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
            rows = await cursor.fetchall()

            return list(rows)

    async def print_full_scoreboard(self) -> None:
        """
        Print the complete scoreboard to console with optimized queries.

        Displays all challenges and their leaderboards in a formatted console output.
        """
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
