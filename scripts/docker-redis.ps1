# Redis for local dev. Matches REDIS_URL=redis://localhost:6379/0
# Usage: .\scripts\docker-redis.ps1

$name = "photogenius-redis"
docker ps -a -q -f "name=^${name}$" | ForEach-Object { docker rm -f $_ 2>$null }
docker run -d --name $name -p 6379:6379 redis:7-alpine
Write-Host "Redis: localhost:6379 (REDIS_URL=redis://localhost:6379/0)"
