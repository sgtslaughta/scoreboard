"""
Web route handlers for CTF scoreboard.
"""

from datetime import datetime
from typing import List, Dict, Any
from aiohttp import web
from jinja2 import Environment, FileSystemLoader


class WebHandlers:
    """Handles web routes and responses."""

    def __init__(
        self,
        db_manager: Any,
        config: Any,
        templates_path: str = "src/templates",
    ) -> None:
        self.db = db_manager
        self.config = config

        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_path),
            auto_reload=False,  # Disable auto-reload for performance
            cache_size=50,  # Cache up to 50 templates
        )

    def calculate_ranks_with_ties(
        self,
        leaderboard_data: List[Any],
    ) -> List[Dict[str, Any]]:
        """
        Calculate ranks accounting for ties (same scores get same rank).

        @param leaderboard_data: List of tuples containing player score data
        @return: List of dictionaries with ranking information and tie indicators
        """
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

    async def web_index(
        self,
        _: web.Request,
    ) -> web.Response:
        """
        Web interface main page.

        @param _: Unused request parameter
        @return: HTTP response with rendered index page
        """
        # Use optimized single-query method to get all challenge data
        challenges_data = await self.db.get_all_challenge_data_optimized()

        template = self.jinja_env.get_template("index.html")
        html = template.render(
            title="Home", challenges=challenges_data, config=self.config
        )
        return web.Response(text=html, content_type="text/html")

    async def web_challenge_detail(
        self,
        request: web.Request,
    ) -> web.Response:
        """
        Web interface challenge detail page.

        @param request: HTTP request object containing challenge name
        @return: HTTP response with rendered challenge detail page
        """
        challenge_name = request.match_info["challenge"]
        leaderboard_data = await self.db.get_challenge_leaderboard(challenge_name, 50)

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
            title=challenge_name,
            challenge_name=challenge_name,
            leaderboard=leaderboard,
            config=self.config,
        )
        return web.Response(text=html, content_type="text/html")

    async def web_player_rankings(
        self,
        _: web.Request,
    ) -> web.Response:
        """
        Web interface player rankings page.

        @param _: Unused request parameter
        @return: HTTP response with rendered player rankings page or 404 if disabled
        """
        # Check if player rankings are enabled
        if not self.config.is_feature_enabled("player_rankings_enabled"):
            return web.Response(
                text="Player rankings are disabled",
                status=404,
                content_type="text/plain",
            )

        player_rankings = await self.db.get_player_rankings()

        template = self.jinja_env.get_template("player_rankings.html")
        html = template.render(
            title="Player Rankings", players=player_rankings, config=self.config
        )
        return web.Response(text=html, content_type="text/html")

    async def web_player_details(
        self,
        request: web.Request,
    ) -> web.Response:
        """
        Web interface player details page.

        @param request: HTTP request object containing player name
        @return: HTTP response with rendered player details page or 404 if disabled
        """
        # Check if player rankings are enabled
        if not self.config.is_feature_enabled("player_rankings_enabled"):
            return web.Response(
                text="Player details are disabled",
                status=404,
                content_type="text/plain",
            )

        player_name = request.match_info["player"]
        player_details = await self.db.get_player_details(player_name)

        # Format details for display
        challenges = []

        for challenge, score, solve_code, timestamp in player_details:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
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
            config=self.config,
        )

        return web.Response(text=html, content_type="text/html")

    async def web_api_challenges(
        self,
        _: web.Request,
    ) -> web.Response:
        """
        API endpoint for challenges.

        @param _: Unused request parameter
        @return: JSON response containing list of all challenges
        """
        challenges = await self.db.get_all_challenges()
        return web.json_response({"challenges": challenges})

    async def web_api_leaderboard(
        self,
        request: web.Request,
    ) -> web.Response:
        """
        API endpoint for leaderboard.

        @param request: HTTP request object containing challenge name and optional limit
        @return: JSON response containing leaderboard data for specified challenge
        """
        challenge = request.match_info["challenge"]
        limit = int(request.query.get("limit", 10))
        leaderboard = await self.db.get_challenge_leaderboard(challenge, limit)

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
