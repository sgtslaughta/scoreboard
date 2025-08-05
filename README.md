# 🏆 CTF Scoreboard System

- [🏆 CTF Scoreboard System](#-ctf-scoreboard-system)
  - [✨ Features](#-features)
  - [🚀 Setup](#-setup)
    - [uv](#uv)
    - [venv](#venv)
  - [💻 Usage](#-usage)
  - [⚙️ CLI Arguments](#️-cli-arguments)
  - [📡 Submission Protocol](#-submission-protocol)
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
python -m uv venv
source ./venv/bin/activate  # or .\.venv\Scripts\activate on Windows
uv pip install -r requirements.txt
```

### venv

```bash
git clone <repository-url>
cd scoreboard
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## 💻 Usage

```bash
# Default: TCP on :8080, web on :8081, saves to scoreboard.db
python scoreboard.py

# Custom ports and database
python scoreboard.py 9000 9001 my_ctf.db
```

## ⚙️ CLI Arguments

| Argument      | Type       | Description                           | Default         | Example       |
| ------------- | ---------- | ------------------------------------- | --------------- | ------------- |
| `socket_port` | Positional | TCP server port for score submissions | `8080`          | `9000`        |
| `web_port`    | Positional | Web interface port                    | `8081`          | `9001`        |
| `db_file`     | Positional | SQLite database file path             | `scoreboard.db` | `ctf_2024.db` |
| `--help`      | Flag       | Show usage information                | -               | -             |

**Argument Types:**
- **Positional**: Must be provided in order (socket_port, web_port, db_file)
- **Flag**: Can be used independently with `--help`

**📋 Usage Examples:**
```bash
python scoreboard.py                    # Use all defaults
python scoreboard.py 9000               # Custom TCP port
python scoreboard.py 9000 9001          # Custom TCP and web ports  
python scoreboard.py 9000 9001 my.db    # Custom ports and database
python scoreboard.py --help             # Show help
```

## 📡 Submission Protocol

Submit scores via TCP using format: `name,challenge,score,solve_code`

```bash
# Example
echo "Alice,RSA_Baby,42,print('Hello World!')" | nc localhost 8080
```

**⚠️ Note**: Lower scores are better (golf scoring).

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

