# 🏆 CTF Scoreboard System

- [🏆 CTF Scoreboard System](#-ctf-scoreboard-system)
  - [✨ Features](#-features)
  - [🚀 Setup](#-setup)
    - [uv](#uv)
    - [venv](#venv)
  - [💻 Usage](#-usage)
  - [⚙️ CLI Arguments](#️-cli-arguments)
  - [🔧 Configuration](#-configuration)
    - [📋 Configuration File Structure](#-configuration-file-structure)
    - [🎯 Configuration Options](#-configuration-options)
      - [CTF Settings](#ctf-settings)
      - [Scoring System](#scoring-system)
      - [Feature Toggles](#feature-toggles)
      - [User Interface](#user-interface)
      - [Submission Rules](#submission-rules)
    - [🔄 Configuration Behavior](#-configuration-behavior)
    - [🎮 Gameplay Impact](#-gameplay-impact)
      - [Golf Scoring (default)](#golf-scoring-default)
      - [Standard Scoring](#standard-scoring)
      - [Optional Solutions](#optional-solutions)
    - [🛠️ Advanced Configuration](#️-advanced-configuration)
  - [📡 Submission Protocol](#-submission-protocol)
    - [Default Format (solutions required)](#default-format-solutions-required)
    - [Optional Solutions Format](#optional-solutions-format)
  - [🧪 Testing](#-testing)
  - [🌐 Web Interface](#-web-interface)
  - [🔌 API](#-api)
  - [💾 Database](#-database)
  - [🔒 Security](#-security)


## ✨ Features

- **🔄 Dual interfaces**: TCP for automated submissions, web for monitoring
- **✅ Solution verification**: Players submit code with scores
- **⚡ Performance optimized**: Async Python with caching
- **🎨 Professional UI**: Responsive design with dark/light themes
- **📱 Mobile friendly**: Works on all devices

## 🚀 Setup

### uv

```bash
git clone <repository-url>
cd scoreboard

uv venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\activate on Windows

uv pip install -r requirements.txt
```

### venv

```bash
git clone <repository-url>
cd scoreboard

python -m venv .venv
source .venv/bin/activate  # or venv\Scripts\activate on Windows

pip install -r requirements.txt
```

## 💻 Usage

```bash
# Default: TCP on :8080, web on :8081, saves to scoreboard.db
python app.py
```

## ⚙️ CLI Arguments

| Argument        | Type  | Description                           | Default           | Example                   |
| --------------- | ----- | ------------------------------------- | ----------------- | ------------------------- |
| `--socket-port` | Named | TCP server port for score submissions | `8080`            | `--socket-port 9000`      |
| `--web-port`    | Named | Web interface port                    | `8081`            | `--web-port 9001`         |
| `--db`          | Named | SQLite database file path             | `scoreboard.db`   | `--db ctf_2024.db`        |
| `--config`      | Named | Configuration file path               | `ctf_config.json` | `--config my_config.json` |
| `--host`        | Named | Host to bind servers to               | `0.0.0.0`         | `--host localhost`        |
| `--help`        | Flag  | Show usage information                | -                 | -                         |

**📋 Usage Examples:**
```bash
python app.py                                    # Use all defaults
python app.py --socket-port 9000                 # Custom TCP port
python app.py --web-port 9001 --db my.db         # Custom web port and database
python app.py --config custom_ctf.json           # Use custom configuration
python app.py --help                             # Show help
```

## 🔧 Configuration

The scoreboard system uses a JSON configuration file (`ctf_config.json`) that provides extensive customization options. If the file doesn't exist, a default configuration will be created automatically.

### 📋 Configuration File Structure

```json
{
  "ctf_name": "CTF Scoreboard",
  "scoring": {
    "scoring_type": "golf", 
    "allow_ties": true,
    "show_scores": true
  },
  "features": {
    "solutions_enabled": true,
    "player_rankings_enabled": true,
    "live_updates": true,
    "challenge_categories": false
  },
  "ui": {
    "theme": "competitive",
    "show_timestamps": true,
    "show_client_ips": false,
    "max_leaderboard_entries": 100
  },
  "submission": {
    "require_solutions": true,
    "max_solution_length": 10000,
    "allowed_file_types": [".py", ".sh", ".txt", ".c", ".cpp", ".java", ".js"]
  }
}
```

### 🎯 Configuration Options

#### CTF Settings
- **`ctf_name`**: Display name for the competition (string)

#### Scoring System
- **`scoring_type`**: Scoring system type:
  - `"golf"`: Lower scores are better, displayed ascending (fastest times, fewest attempts)
  - `"standard"`: Higher scores are better, displayed descending (points-based challenges)
- **`allow_ties`**: Whether tied scores are permitted (boolean)
- **`show_scores`**: Display score values in UI (boolean)

#### Feature Toggles
- **`solutions_enabled`**: Show/hide solution code viewing (boolean)
- **`player_rankings_enabled`**: Enable player rankings pages and links (boolean)
- **`live_updates`**: Enable real-time updates (boolean)
- **`challenge_categories`**: Group challenges by category (boolean, future feature)

#### User Interface
- **`theme`**: Visual theme (`"competitive"`, `"classic"`, or `"minimal"`)
- **`show_timestamps`**: Display submission timestamps (boolean)
- **`show_client_ips`**: Show client IP addresses (boolean)
- **`max_leaderboard_entries`**: Maximum entries shown per leaderboard (integer)

#### Submission Rules
- **`require_solutions`**: Whether solution code is mandatory (boolean)
- **`max_solution_length`**: Maximum characters in solution code (integer)
- **`allowed_file_types`**: Permitted file extensions for uploads (array)

### 🔄 Configuration Behavior

- **Auto-creation**: Missing config files are created with defaults
- **Validation**: Invalid values are corrected with warnings
- **Merge Strategy**: Partial configs are merged with defaults
- **Hot Reload**: Restart required for config changes

### 🎮 Gameplay Impact

#### Golf Scoring (default)
```bash
# Lower scores are better, automatically sorted ascending (best first)
echo "Alice,crypto1,45,solution_code" | nc localhost 8080  # Better score (shown higher on leaderboard)
echo "Bob,crypto1,67,solution_code" | nc localhost 8080    # Worse score (shown lower on leaderboard)
```

#### Standard Scoring 
```bash  
# Higher scores are better, automatically sorted descending (best first)
echo "Alice,pwn1,1500,exploit_code" | nc localhost 8080    # Better score (shown higher on leaderboard)
echo "Bob,pwn1,1200,exploit_code" | nc localhost 8080      # Worse score (shown lower on leaderboard)
```

#### Optional Solutions
When `require_solutions` is `false`, the solution code becomes optional:
```bash
# Both formats are accepted:
echo "Alice,crypto1,45,solution_code" | nc localhost 8080  # With solution
echo "Bob,crypto1,67" | nc localhost 8080                  # Without solution
```

### 🛠️ Advanced Configuration

**Custom Configuration File:**
```bash
python app.py --config /path/to/custom_config.json
```

**Environment-Specific Configs:**
```bash
# Development
python app.py --config dev_config.json

# Production  
python app.py --config prod_config.json

# Competition-specific
python app.py --config bsides_2024.json
```

## 📡 Submission Protocol

The TCP submission format depends on your configuration:

### Default Format (solutions required)
```bash
# Format: name,challenge,score,solve_code
echo "Alice,RSA_Baby,42,print('Hello World!')" | nc localhost 8080
```

### Optional Solutions Format 
When `require_solutions` is `false` in config:
```bash
# With solution
echo "Alice,RSA_Baby,42,print('Hello World!')" | nc localhost 8080

# Without solution  
echo "Bob,RSA_Baby,38" | nc localhost 8080
```

**⚠️ Scoring**: Default is golf scoring (lower is better, shown ascending). Can be changed to standard scoring (higher is better, shown descending) in configuration.

## 🧪 Testing

Generate realistic test data:

```bash
python test_client.py --generate  # Creates 50 challenges with multiple players
```

## 🌐 Web Interface

Visit `http://localhost:8081` for:
- 🏅 Challenge overview and leaderboards
- 👥 Player rankings and profiles  
- 💻 Solution code viewing
- 🌙 Dark/light theme toggle

## 🔌 API

- `GET /api/challenges` - List challenges
- `GET /api/leaderboard/{challenge}?limit=N` - Challenge rankings

## 💾 Database

SQLite with optimized schema and indexes. Uses WAL mode for better concurrency.

## 🔒 Security

- 🛡️ HTML escaping prevents XSS
- 💉 Parameterized queries prevent SQL injection
- ✅ Input validation on all submissions
- 🚦 Rate limiting via asyncio semaphores

