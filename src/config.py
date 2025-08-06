"""
Configuration management for CTF scoreboard.
Supports both JSON file configuration and environment variable overrides.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class CTFConfig:
    """Configuration management for CTF scoreboard."""

    DEFAULT_CONFIG = {
        "ctf_name": "CTF Scoreboard",
        "scoring": {
            "scoring_type": "golf",  # golf (lower is better) or standard (higher is better)
            "allow_ties": True,
            "show_scores": True,
        },
        "features": {
            "solutions_enabled": True,
            "player_rankings_enabled": True,
            "live_updates": True,
            "challenge_categories": False,
        },
        "ui": {
            "theme": "competitive",  # competitive, classic, minimal
            "show_timestamps": True,
            "show_client_ips": False,
            "max_leaderboard_entries": 100,
        },
        "submission": {
            "require_solutions": True,
            "max_solution_length": 10000,
            "allowed_file_types": [".py", ".sh", ".txt", ".c", ".cpp", ".java", ".js"],
        },
    }

    def __init__(
        self,
        config_path: str = "ctf_config.json",
    ) -> None:
        """Initialize configuration from file, environment variables, or defaults."""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._apply_env_overrides()
        self._validate_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from JSON file or create default.

        @return: Dictionary containing the loaded configuration
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)

                # Merge with defaults to ensure all keys exist
                config = self.DEFAULT_CONFIG.copy()
                self._deep_merge(config, loaded_config)
                return config

            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config from {self.config_path}: {e}")
                print("Using default configuration")
                return self.DEFAULT_CONFIG.copy()
        else:
            # Create default config file
            self._create_default_config()
            return self.DEFAULT_CONFIG.copy()

    def _deep_merge(
        self,
        base_dict: Dict[str, Any],
        update_dict: Dict[str, Any],
    ) -> None:
        """
        Recursively merge dictionaries.

        @param base_dict: Base dictionary to merge into
        @param update_dict: Dictionary with updates to merge
        """
        for key, value in update_dict.items():
            if (
                key in base_dict
                and isinstance(base_dict[key], dict)
                and isinstance(value, dict)
            ):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value

    def _apply_env_overrides(self) -> None:
        """
        Apply environment variable overrides to configuration.
        
        Environment variables follow the pattern: SECTION_KEY (e.g., CTF_NAME, SCORING_TYPE)
        """
        env_mappings = {
            # Basic configuration
            "CTF_NAME": ("ctf_name",),
            
            # Scoring configuration
            "SCORING_TYPE": ("scoring", "scoring_type"),
            "ALLOW_TIES": ("scoring", "allow_ties"),
            "SHOW_SCORES": ("scoring", "show_scores"),
            
            # Features
            "SOLUTIONS_ENABLED": ("features", "solutions_enabled"),
            "PLAYER_RANKINGS_ENABLED": ("features", "player_rankings_enabled"),
            "LIVE_UPDATES": ("features", "live_updates"),
            "CHALLENGE_CATEGORIES": ("features", "challenge_categories"),
            
            # UI configuration
            "THEME": ("ui", "theme"),
            "SHOW_TIMESTAMPS": ("ui", "show_timestamps"),
            "SHOW_CLIENT_IPS": ("ui", "show_client_ips"),
            "MAX_LEADERBOARD_ENTRIES": ("ui", "max_leaderboard_entries"),
            
            # Submission configuration
            "REQUIRE_SOLUTIONS": ("submission", "require_solutions"),
            "MAX_SOLUTION_LENGTH": ("submission", "max_solution_length"),
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert string values to appropriate types
                converted_value = self._convert_env_value(env_value)
                self._set_nested_config(config_path, converted_value)

    def _convert_env_value(self, value: str) -> Any:
        """
        Convert environment variable string to appropriate type.
        
        @param value: String value from environment variable
        @return: Converted value (bool, int, or string)
        """
        # Handle boolean values
        if value.lower() in ("true", "1", "yes", "on"):
            return True
        elif value.lower() in ("false", "0", "no", "off"):
            return False
        
        # Handle integer values
        try:
            return int(value)
        except ValueError:
            pass
        
        # Return as string
        return value

    def _set_nested_config(self, path: tuple, value: Any) -> None:
        """
        Set a nested configuration value using a path tuple.
        
        @param path: Tuple representing the nested path (e.g., ("scoring", "scoring_type"))
        @param value: Value to set
        """
        current = self.config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    def _create_default_config(self) -> None:
        """
        Create a default configuration file.

        Writes the default configuration to the configured file path.
        """
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.DEFAULT_CONFIG, f, indent=2)
            print(f"Created default configuration file: {self.config_path}")
        except IOError as e:
            print(f"Could not create config file {self.config_path}: {e}")

    def _validate_config(self) -> None:
        """
        Validate configuration values.

        Checks configuration values for validity and sets defaults for invalid values.
        """
        # Validate scoring_type
        if self.config["scoring"]["scoring_type"] not in ["golf", "standard"]:
            print("Warning: Invalid scoring_type, using 'golf'")
            self.config["scoring"]["scoring_type"] = "golf"

        # Validate theme
        if self.config["ui"]["theme"] not in ["competitive", "classic", "minimal"]:
            print("Warning: Invalid theme, using 'competitive'")
            self.config["ui"]["theme"] = "competitive"

        # Validate max_solution_length
        if self.config["submission"]["max_solution_length"] <= 0:
            print("Warning: Invalid max_solution_length, using 10000")
            self.config["submission"]["max_solution_length"] = 10000

        # Validate max_leaderboard_entries
        if self.config["ui"]["max_leaderboard_entries"] <= 0:
            print("Warning: Invalid max_leaderboard_entries, using 100")
            self.config["ui"]["max_leaderboard_entries"] = 100

    def get(
        self,
        *keys: str,
    ) -> Any:
        """
        Get nested configuration value using dot notation.

        @param keys: Variable arguments representing nested keys to traverse
        @return: Configuration value at the specified path, None if not found
        """
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    def is_feature_enabled(
        self,
        feature_name: str,
    ) -> bool:
        """
        Check if a feature is enabled.

        @param feature_name: Name of the feature to check
        @return: True if feature is enabled, False otherwise
        """
        return self.get("features", feature_name) is True

    def get_sort_order(self) -> str:
        """
        Get the sort order for scores based on scoring type.

        @return: "ASC" for golf scoring, "DESC" for standard scoring
        """
        scoring_type = self.get("scoring", "scoring_type")

        # Golf scoring: lower scores are better (ASC shows best first)
        # Standard scoring: higher scores are better (DESC shows best first)
        if scoring_type == "golf":
            return "ASC"  # Show lowest scores first
        else:  # standard
            return "DESC"  # Show highest scores first

    def save_config(self) -> bool:
        """
        Save current configuration to file.

        @return: True if saved successfully, False on error
        """
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            return True
        except IOError as e:
            print(f"Could not save config file {self.config_path}: {e}")
            return False
