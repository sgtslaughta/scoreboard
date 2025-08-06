# CTF Scoreboard Docker Setup

This document provides instructions for running the CTF Scoreboard application using Docker and Docker Compose.

## Quick Start

1. **Clone the repository and navigate to the project directory**
   ```bash
   cd scoreboard
   ```

2. **Create environment configuration**
   ```bash
   cp env.example .env
   # Edit .env file with your desired configuration
   ```

3. **Start the application**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Web interface: http://localhost:8081
   - TCP socket: localhost:8080

## Configuration

### Environment Variables

The application supports configuration through environment variables. See `env.example` for all available options:

#### Server Configuration
- `HOST`: Host to bind servers to (default: 0.0.0.0)
- `SOCKET_PORT`: TCP socket port (default: 8080)
- `WEB_PORT`: Web interface port (default: 8081)
- `DB_PATH`: Database file path (default: /app/data/scoreboard.db)
- `CONFIG_PATH`: Configuration file path (default: /app/data/ctf_config.json)

#### CTF Configuration
- `CTF_NAME`: Name of the CTF competition
- `SCORING_TYPE`: "golf" (lower is better) or "standard" (higher is better)
- `ALLOW_TIES`: Allow tied scores (true/false)
- `SHOW_SCORES`: Show scores on leaderboard (true/false)

#### Feature Toggles
- `SOLUTIONS_ENABLED`: Enable solution submission (true/false)
- `PLAYER_RANKINGS_ENABLED`: Enable player rankings page (true/false)
- `LIVE_UPDATES`: Enable live updates (true/false)
- `CHALLENGE_CATEGORIES`: Enable challenge categories (true/false)

#### UI Configuration
- `THEME`: Theme ("competitive", "classic", "minimal")
- `SHOW_TIMESTAMPS`: Show timestamps (true/false)
- `SHOW_CLIENT_IPS`: Show client IPs (true/false)
- `MAX_LEADERBOARD_ENTRIES`: Maximum leaderboard entries (number)

#### Submission Configuration
- `REQUIRE_SOLUTIONS`: Require solution files (true/false)
- `MAX_SOLUTION_LENGTH`: Maximum solution length in characters (number)

### Configuration Files

The application also supports JSON configuration files. The default configuration is loaded from `ctf_config.json`, which can be customized and mounted into the container.

## Docker Commands

### Build and Start
```bash
# Build and start in detached mode
docker-compose up -d

# Build and start with logs
docker-compose up

# Build only
docker-compose build
```

### Management
```bash
# Stop the application
docker-compose down

# Restart the application
docker-compose restart

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f scoreboard
```

### Data Management
```bash
# Backup database
docker-compose exec scoreboard cp /app/data/scoreboard.db /app/data/backup.db

# Access container shell
docker-compose exec scoreboard /bin/bash

# View container status
docker-compose ps
```

## Volumes and Data Persistence

The Docker setup uses named volumes for data persistence:

- `scoreboard_data`: Contains the SQLite database and configuration files
- `scoreboard_logs`: Contains application logs

Data persists between container restarts and updates.

### Backup and Restore

#### Backup
```bash
# Create backup directory
mkdir backups

# Backup data volume
docker run --rm -v scoreboard_scoreboard_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/scoreboard_data_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .

# Backup logs volume
docker run --rm -v scoreboard_scoreboard_logs:/data -v $(pwd)/backups:/backup alpine tar czf /backup/scoreboard_logs_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
```

#### Restore
```bash
# Restore data volume (replace BACKUP_FILE with actual backup filename)
docker run --rm -v scoreboard_scoreboard_data:/data -v $(pwd)/backups:/backup alpine tar xzf /backup/BACKUP_FILE -C /data
```

## Network Configuration

The application creates a custom network `ctf-scoreboard-network` for container communication.

### Port Mapping

By default, the following ports are exposed:
- `8080`: TCP socket server
- `8081`: Web interface

You can customize port mappings by modifying the `docker-compose.yml` file or setting environment variables:

```bash
SOCKET_PORT=9080 WEB_PORT=9081 docker-compose up
```

## Security Considerations

1. **Network Security**: The application binds to `0.0.0.0` by default for Docker compatibility. In production, consider using a reverse proxy.

2. **Volume Permissions**: Ensure proper file permissions on mounted volumes.

3. **Environment Variables**: Keep sensitive configuration in `.env` files and never commit them to version control.

4. **Resource Limits**: The Docker Compose configuration includes resource limits. Adjust based on your requirements.

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Check what's using the port
   netstat -tulpn | grep :8081
   
   # Change port in .env file
   WEB_PORT=8082
   ```

2. **Permission Denied on Volumes**
   ```bash
   # Fix volume permissions
   docker-compose exec scoreboard chown -R ctf:ctf /app/data /app/logs
   ```

3. **Container Won't Start**
   ```bash
   # Check logs
   docker-compose logs scoreboard
   
   # Check container status
   docker-compose ps
   ```

### Health Checks

The container includes health checks that verify the web interface is responding:

```bash
# Check health status
docker-compose ps
docker inspect scoreboard_scoreboard_1 | grep -A 20 '"Health"'
```

## Development

For development with Docker:

1. **Development Override**
   ```bash
   # Create docker-compose.override.yml for development settings
   version: '3.8'
   services:
     scoreboard:
       volumes:
         - .:/app
       environment:
         - PYTHONPATH=/app
   ```

2. **Live Reload**
   ```bash
   # Mount source code for development
   docker-compose -f docker-compose.yml -f docker-compose.override.yml up
   ```

## Production Deployment

For production deployment:

1. **Use specific image tags** instead of `latest`
2. **Set up proper logging** with log rotation
3. **Configure reverse proxy** (nginx/Apache)
4. **Set up monitoring** and health checks
5. **Configure backup strategy** for data volumes
6. **Use secrets management** for sensitive configuration

### Example Production Configuration

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  scoreboard:
    image: ctf-scoreboard:1.0.0
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    environment:
      - SHOW_CLIENT_IPS=false
      - THEME=competitive
```

Deploy with:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```