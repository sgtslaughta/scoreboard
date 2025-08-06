"""
CTF Scoreboard System - A scoreboard for Capture The Flag competitions.

This package provides:
- TCP socket server for automated score submissions
- Web interface for viewing leaderboards and player rankings
- Configurable scoring systems (golf vs standard)
- Feature toggles for solutions and rankings
- UI with dark/light themes
"""

from .config import CTFConfig
from .database import DatabaseManager
from .web_handlers import WebHandlers
from .tcp_server import TCPServer
from .scoreboard import ScoreboardSystem

__version__ = "2.0.0"
__author__ = "CTF Scoreboard Contributors"

__all__ = [
    "CTFConfig",
    "DatabaseManager",
    "WebHandlers",
    "TCPServer",
    "ScoreboardSystem",
]
