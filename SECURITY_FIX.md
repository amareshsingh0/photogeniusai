# Security Fix - Bot Scanner Attack

## Problem
Your server is under **automated bot attack** scanning for sensitive files:
- `.env` files
- `phpinfo.php`
- AWS credentials
- Config files

These are **common hacker tools** looking for exposed secrets.

## Quick Fix Commands

### 1. Block Scanner IPs (Nginx)
```bash
# Create security config
sudo nano /etc/nginx/conf.d/security.conf
```

Add this:
```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;

# Block known bad patterns
map $request_uri $is_bad_request {
    default 0;
    ~*\.env 1;
    ~*phpinfo 1;
    ~*\.aws 1;
    ~*\.bak 1;
    ~*\.old 1;
    ~*\.git 1;
    ~*config\.php 1;
    ~*database\.js 1;
    ~*settings\.py 1;
}
```

### 2. Update Main Nginx Config
```bash
sudo nano /etc/nginx/sites-available/photogenius
```

Add inside `server` block:
```nginx
# Block bad requests immediately
if ($is_bad_request = 1) {
    return 444;  # Drop connection without response
}

# Rate limiting
limit_req zone=general burst=20 nodelay;

# Block specific paths
location ~ /\. {
    deny all;
    return 404;
}

location ~ \.(env|git|bak|old|aws)$ {
    deny all;
    return 404;
}
```

### 3. Add Fail2Ban Protection
```bash
# Install fail2ban
sudo apt-get install fail2ban -y

# Create custom jail
sudo nano /etc/fail2ban/jail.local
```

Add:
```ini
[nginx-bad-requests]
enabled = true
port = http,https
filter = nginx-bad-requests
logpath = /var/log/nginx/access.log
maxretry = 5
bantime = 3600
findtime = 300

[nginx-404]
enabled = true
port = http,https
filter = nginx-404
logpath = /var/log/nginx/access.log
maxretry = 20
bantime = 600
findtime = 300
```

### 4. Create Fail2Ban Filters
```bash
# Bad requests filter
sudo nano /etc/fail2ban/filter.d/nginx-bad-requests.conf
```

Add:
```ini
[Definition]
failregex = ^<HOST> .* "(GET|POST|HEAD) /.*\.(env|git|aws|bak|old|config\.php|phpinfo\.php).*" .*$
ignoreregex =
```

```bash
# 404 filter
sudo nano /etc/fail2ban/filter.d/nginx-404.conf
```

Add:
```ini
[Definition]
failregex = ^<HOST> .* "(GET|POST) .* HTTP.*" 404 .*$
ignoreregex =
```

### 5. Restart Services
```bash
# Restart nginx
sudo nginx -t
sudo systemctl restart nginx

# Restart fail2ban
sudo systemctl restart fail2ban
sudo fail2ban-client status
```

### 6. Monitor Banned IPs
```bash
# Check current bans
sudo fail2ban-client status nginx-bad-requests
sudo fail2ban-client status nginx-404

# Unban IP if needed
sudo fail2ban-client set nginx-bad-requests unbanip <IP>
```

---

## FastAPI Application Level Protection

Add middleware in `apps/api/app/main.py`:

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
import re

# Bad path patterns
BAD_PATTERNS = [
    r'\.env', r'phpinfo', r'\.aws', r'\.git', r'\.bak',
    r'\.old', r'config\.php', r'database\.js', r'settings\.py',
    r'\.env\.(prod|local|example)', r'swagger\.json'
]
BAD_REGEX = re.compile('|'.join(BAD_PATTERNS), re.IGNORECASE)

@app.middleware("http")
async def block_scanner_bots(request: Request, call_next):
    path = request.url.path

    # Block bad patterns
    if BAD_REGEX.search(path):
        logger.warning(f"[SECURITY] Blocked scanner: {request.client.host} → {path}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Not Found"}
        )

    response = await call_next(request)
    return response
```

---

## Quality Critic JSON Parse Error Fix

The error `'beast_gates_passed'` means Quality Critic response format changed.

### Fix in `apps/api/app/services/smart/quality_critic.py`:

```bash
grep -n "beast_gates_passed" apps/api/app/services/smart/quality_critic.py
```

Then check the actual dict key being used. Likely should be:
- `beast_gates` instead of `beast_gates_passed`
- Or add fallback: `quality_result.get("beast_gates_passed", 0)`

---

## Summary of Security Measures

✅ **Nginx Level:**
- Rate limiting (10 req/sec general, 30 req/sec API)
- Block `.env`, `.git`, `.aws`, `phpinfo.php` paths
- Return 444 (drop connection) for bad requests

✅ **Fail2Ban Level:**
- Auto-ban IPs after 5 bad requests
- Ban duration: 1 hour
- 404 protection: ban after 20 × 404 in 5 minutes

✅ **Application Level:**
- FastAPI middleware to reject bad paths
- Log security events
- Return 404 (don't leak info about blocks)

✅ **Monitoring:**
- `sudo fail2ban-client status` - see active jails
- `sudo tail -f /var/log/nginx/access.log | grep 404` - watch attacks
- `sudo tail -f /var/log/fail2ban.log` - see bans

---

## Test Security
```bash
# From different machine, try:
curl http://your-server/.env
# Should get 404 immediately

curl http://your-server/phpinfo.php
# Should get 404 immediately

# Try 6+ times rapidly:
for i in {1..10}; do curl http://your-server/.env; done
# After 5th attempt, IP should be banned
```

---

**PRIORITY:** Do this NOW - your server is actively being scanned!
