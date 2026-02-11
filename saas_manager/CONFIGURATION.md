# SaaS Manager Configuration Guide

Complete setup guide for SaaS Manager module on Odoo 18.

## 📋 Table of Contents

1. [System Requirements](#system-requirements)
2. [Odoo Configuration](#odoo-configuration)
3. [PostgreSQL Setup](#postgresql-setup)
4. [Reverse Proxy Configuration](#reverse-proxy-configuration)
5. [DNS Configuration](#dns-configuration)
6. [Module Configuration](#module-configuration)
7. [Security Hardening](#security-hardening)
8. [Monitoring Setup](#monitoring-setup)

## 🖥️ System Requirements

### Minimum Requirements (Testing)
- **OS:** Ubuntu 20.04+ / Debian 11+
- **RAM:** 8 GB
- **CPU:** 4 cores
- **Storage:** 100 GB SSD
- **Network:** Static IP address

### Recommended Requirements (Production)
- **OS:** Ubuntu 22.04 LTS
- **RAM:** 64 GB
- **CPU:** 16 cores
- **Storage:** 500 GB NVMe SSD
- **Network:** Static IP + Domain name

### Software Requirements
- **Odoo:** 18.0
- **PostgreSQL:** 12+ (14+ recommended)
- **Python:** 3.10+
- **Nginx/Traefik:** Latest stable
- **SSL:** Let's Encrypt

## ⚙️ Odoo Configuration

### Critical odoo.conf Settings

```ini
[options]
# ========================================
# ESSENTIAL FOR SAAS MANAGER
# ========================================

# Database filter - Maps subdomain to database name
# client1.example.com → database "client1"
dbfilter = ^%h$

# ========================================
# PERFORMANCE SETTINGS
# ========================================

# Workers (2 x CPU cores + 1)
workers = 8

# Database connection pool
db_maxconn = 64
db_maxconn_gevent = 64

# Memory limits (per worker)
limit_memory_hard = 2684354560  # 2.5 GB
limit_memory_soft = 2147483648  # 2 GB
limit_request = 8192
limit_time_cpu = 600
limit_time_real = 1200

# ========================================
# MULTI-DB SETTINGS
# ========================================

# Allow database management
list_db = False  # Disable database list for security
dbfilter_from_header = False

# Admin password (REQUIRED FOR RPC TEMPLATE CREATION)
# This is used by RPC API to create template databases
# MUST be a strong password in production
admin_passwd = CHANGE_ME_STRONG_PASSWORD  # 20+ characters recommended
# Admin password (CHANGE IN PRODUCTION)
admin_passwd = CHANGE_ME_STRONG_PASSWORD

# ========================================
# LOGGING
# ========================================

logfile = /var/log/odoo/odoo-server.log
log_level = info
log_handler = :INFO

# ========================================
# PATHS
# ========================================

addons_path = /opt/odoo/addons,/opt/odoo/custom-addons
data_dir = /var/lib/odoo

# ========================================
# DATABASE
# ========================================

db_host = localhost
db_port = 5432
db_user = odoo
db_password = CHANGE_ME_DB_PASSWORD
db_name = False  # Required for multi-db

# ========================================
# NETWORK (RPC API REQUIRED)
# NETWORK
# ========================================

http_interface = 0.0.0.0
http_port = 8069
proxy_mode = True  # Essential for reverse proxy

# RPC endpoint available at: http://localhost:8069/jsonrpc
# Used for template database creation via RPC API
# ========================================
# XMLRPC (for odoorpc provisioning)
# ========================================

xmlrpc_interface = 127.0.0.1
xmlrpc_port = 8069
```

### Restart Odoo

```bash
sudo systemctl restart odoo
sudo systemctl status odoo
```

## 🗄️ PostgreSQL Setup

### 1. Create PostgreSQL User

```sql
-- Connect as postgres user
sudo -u postgres psql

-- Create Odoo user with template creation rights
CREATE USER odoo WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
ALTER USER odoo CREATEDB;
ALTER USER odoo WITH CREATEROLE;

-- Grant template creation permissions
ALTER USER odoo WITH SUPERUSER;  -- For template cloning
-- OR for more restricted setup:
GRANT CREATE ON DATABASE template1 TO odoo;
```

### 2. PostgreSQL Configuration

Edit `/etc/postgresql/14/main/postgresql.conf`:

```ini
# Memory settings (for 64GB RAM server)
shared_buffers = 16GB
effective_cache_size = 48GB
maintenance_work_mem = 2GB
work_mem = 64MB

# Connection settings
max_connections = 200

# Performance
random_page_cost = 1.1  # For SSD
effective_io_concurrency = 200
```

Edit `/etc/postgresql/14/main/pg_hba.conf`:

```
# Allow local connections
local   all             odoo                                    md5
host    all             odoo            127.0.0.1/32            md5
host    all             odoo            ::1/128                 md5
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
sudo systemctl status postgresql
```

### 3. Create Template Databases

**RECOMMENDED: Via Odoo UI (RPC-based - Automatic)**

After module installation:
1. Go to **SaaS Manager → Configuration → Templates**
2. Select a template (e.g., "Restaurant Template")
3. Click **"Create Template DB"** button
4. Wait 5-10 minutes for completion
5. Template will be automatically marked as "Ready" ✓
6. Base modules (base, web, mail, portal) are pre-installed

**What happens behind the scenes:**
- Creates PostgreSQL database via RPC (`/jsonrpc` endpoint)
- Authenticates to new database
- Installs base modules automatically
- Sets `is_template_ready = True`

**Requirements for RPC approach:**
- `web.base.url` system parameter configured
- `admin_passwd` in odoo.conf configured
- RPC endpoint accessible

**Manual PostgreSQL Creation (Legacy/Testing only)**

```bash
# Option 2: Manual creation (not recommended - skips module installation)
```bash
# Option 1: Via Odoo UI (after module installation)
# Go to SaaS Manager → Configuration → Templates
# Click "Create Template DB" on each template

# Option 2: Manual creation (for testing)
sudo -u postgres psql

CREATE DATABASE template_blank WITH OWNER odoo;
CREATE DATABASE template_restaurant WITH OWNER odoo;
CREATE DATABASE template_ecommerce WITH OWNER odoo;
CREATE DATABASE template_services WITH OWNER odoo;

# Mark as templates (optional - improves performance)
UPDATE pg_database SET datistemplate = TRUE WHERE datname LIKE 'template_%';

# Note: With manual creation, you must manually:
# 1. Initialize each database with Odoo
# 2. Install required modules
# 3. Mark template as ready in SaaS Manager
```

**Verification:**

```bash
# Check templates exist
sudo -u postgres psql -c "\l" | grep template_

# Check template is ready (via Odoo shell)
cd /path/to/odoo
./odoo-bin shell -d your_main_db
>>> env['saas.template'].search([('code', '=', 'restaurant')]).is_template_ready
True
```

## 🌐 Reverse Proxy Configuration

### Option 1: Nginx

Create `/etc/nginx/sites-available/saas-manager`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name *.example.com example.com;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS configuration with wildcard subdomain
server {
    listen 443 ssl http2;
    server_name *.example.com example.com;
    
    # SSL certificates (Let's Encrypt wildcard)
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    
    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Proxy settings
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Host $host;
    proxy_redirect off;
    
    # Odoo upstream
    location / {
        proxy_pass http://localhost:8069;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
    
    # WebSocket support (for Odoo 18)
    location /websocket {
        proxy_pass http://localhost:8072;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Static files
    location ~* /web/static/ {
        proxy_pass http://localhost:8069;
        proxy_cache_valid 200 90m;
        proxy_buffering on;
        expires 864000;
    }
    
    # File upload size
    client_max_body_size 100M;
}
```

Enable and restart:

```bash
sudo ln -s /etc/nginx/sites-available/saas-manager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Option 2: Traefik (Docker)

Create `docker-compose.yml`:

```yaml
version: '3'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.dnschallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.email=admin@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./letsencrypt:/letsencrypt"
    labels:
      - "traefik.http.routers.odoo.rule=HostRegexp(`{subdomain:[a-z0-9-]+}.example.com`)"
      - "traefik.http.routers.odoo.entrypoints=websecure"
      - "traefik.http.routers.odoo.tls.certresolver=letsencrypt"
      - "traefik.http.services.odoo.loadbalancer.server.port=8069"
```

## 🌍 DNS Configuration

### Option 1: Wildcard DNS (Recommended)

Add to your DNS provider (e.g., Cloudflare, Route53):

```
Type    Name                Value           TTL
A       example.com         YOUR_SERVER_IP  300
A       *.example.com       YOUR_SERVER_IP  300
```

### Option 2: Individual Subdomains

For each client instance:

```
Type    Name                    Value           TTL
A       client1.example.com     YOUR_SERVER_IP  300
A       client2.example.com     YOUR_SERVER_IP  300
```

### SSL Certificate (Wildcard)

Using Certbot with DNS challenge:

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get wildcard certificate (requires DNS API access)
sudo certbot certonly --manual --preferred-challenges dns \
  -d example.com -d *.example.com

# Follow prompts to add TXT records to DNS
```

## 🔧 Module Configuration

### 1. System Parameters

After module installation, go to:
**Settings → Technical → Parameters → System Parameters**

Set the following:

```
Key: saas.base_domain
Value: example.com

Key: web.base.url
Value: http://localhost:8069  (or https://your-domain.com in production)
Description: REQUIRED for RPC template creation - used to construct RPC endpoint URL
Key: saas.odoo_host
Value: localhost

Key: saas.odoo_port
Value: 8069
```

### 2. Email Configuration

Configure outgoing mail server in Odoo:
**Settings → Technical → Email → Outgoing Mail Servers**

```
SMTP Server: smtp.gmail.com (or your provider)
SMTP Port: 587
Security: TLS
Username: your-email@example.com
Password: your-password
```

### 3. User Groups

Assign users to SaaS Manager groups:
**Settings → Users & Companies → Users**

Groups:
- **SaaS Manager / User** - Read-only
- **SaaS Manager / Manager** - CRUD instances
- **SaaS Manager / Administrator** - Full access

## 🔌 RPC API Configuration

### Overview

The SaaS Manager uses Odoo's **JSON-RPC API** for template database creation instead of subprocess or direct SQL. This provides better integration, security, and error handling.

### Required Configuration

#### 1. System Parameter: web.base.url

**Location:** Settings → Technical → Parameters → System Parameters

**Value:**
```
Development: http://localhost:8069
Production: https://your-domain.com
```

**Purpose:**
- Used to construct RPC endpoint URL (`{base_url}/jsonrpc`)
- Must be accessible from the Odoo server itself
- Used by `action_create_template_db()` method

**Verification:**
```bash
# Test RPC endpoint is accessible
curl -X POST http://localhost:8069/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "service": "db",
      "method": "list",
      "args": []
    },
    "id": 1
  }'
```

**Expected Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": ["database1", "database2", ...]
}
```

#### 2. Master Password: admin_passwd

**Location:** `/etc/odoo/odoo.conf` (or your odoo.conf path)

**Configuration:**
```ini
[options]
# CRITICAL: Required for RPC database creation
admin_passwd = K9$mP2#vL8@nQ5&xR7!wT3yH6^bN4!mL5

# DO NOT use default 'admin' in production
# Generate strong password: openssl rand -base64 32
```

**Security Requirements:**
- Minimum 20 characters
- Mix of uppercase, lowercase, numbers, symbols
- Never commit to version control
- Rotate quarterly
- Store in secure secrets management (production)

**Generate Strong Password:**
```bash
# Option 1: OpenSSL
openssl rand -base64 32

# Option 2: Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Option 3: pwgen (if installed)
pwgen -s 32 1
```

**Environment Variable Approach (Recommended for Production):**
```bash
# /etc/systemd/system/odoo.service
[Service]
Environment="ADMIN_PASSWD=your_strong_password_here"
ExecStart=/usr/bin/odoo-bin --config=/etc/odoo/odoo.conf

# odoo.conf
[options]
admin_passwd = ${ADMIN_PASSWD}
```

#### 3. Network Access Configuration

**Firewall Rules:**

For **development** (local only):
```bash
# Allow RPC only from localhost
sudo ufw deny 8069/tcp
sudo ufw allow from 127.0.0.1 to any port 8069
```

For **production** (with reverse proxy):
```bash
# RPC should only be accessible internally
# External access via reverse proxy only
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8069/tcp
sudo ufw allow from 10.0.0.0/8 to any port 8069  # Internal network
```

**Reverse Proxy Configuration (Nginx):**

Restrict `/jsonrpc` endpoint to internal use only:

```nginx
# /etc/nginx/sites-available/saas-manager

server {
    listen 443 ssl http2;
    server_name example.com *.example.com;
    
    # ... SSL configuration ...
    
    # Restrict RPC endpoint to internal IPs
    location /jsonrpc {
        # Allow from internal network only
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        allow 192.168.0.0/16;
        deny all;
        
        proxy_pass http://localhost:8069;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeout for database creation
        proxy_read_timeout 600s;
        proxy_connect_timeout 600s;
    }
    
    # Public endpoints
    location / {
        proxy_pass http://localhost:8069;
        # ... standard proxy settings ...
    }
}
```

### RPC Testing & Verification

#### Test 1: List Databases

```bash
curl -X POST http://localhost:8069/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "service": "db",
      "method": "list",
      "args": []
    },
    "id": 1
  }'
```

**Expected Output:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": ["saas_manager_main", "template_blank", ...]
}
```

#### Test 2: Get Odoo Version

```bash
curl -X POST http://localhost:8069/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "service": "common",
      "method": "version",
      "args": []
    },
    "id": 1
  }'
```

**Expected Output:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "server_version": "18.0",
    "server_version_info": [18, 0, 0, "final", 0],
    "protocol_version": 1
  }
}
```

#### Test 3: Test Authentication (Optional)

```bash
curl -X POST http://localhost:8069/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "service": "common",
      "method": "login",
      "args": ["your_database", "admin", "admin"]
    },
    "id": 1
  }'
```

**Expected Output:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": 2  // user_id
}
```

### RPC Security Best Practices

1. **Master Password Security**
   - Never use default 'admin' password
   - Use password manager for generation
   - Store in environment variables or secrets manager
   - Rotate password quarterly
   - Monitor access logs

2. **Network Restrictions**
   - Limit RPC access to localhost/internal network
   - Use reverse proxy with IP whitelist
   - Enable firewall rules
   - Monitor failed RPC attempts

3. **Audit Logging**
   - Enable detailed logging for RPC calls
   - Monitor template creation events
   - Alert on failed RPC authentication
   - Regular log review

4. **SSL/TLS**
   - Always use HTTPS in production
   - Valid SSL certificates
   - TLS 1.2 or higher
   - Strong cipher suites

### RPC Troubleshooting

#### Error: "Failed to connect to Odoo RPC endpoint"

**Check:**
1. Verify Odoo is running: `sudo systemctl status odoo`
2. Check `web.base.url` parameter
3. Test RPC endpoint with curl (see tests above)
4. Check firewall rules: `sudo ufw status`

#### Error: "RPC Error while creating database"

**Check:**
1. Verify `admin_passwd` in odoo.conf
2. Check if database already exists
3. Review PostgreSQL permissions
4. Check Odoo logs: `tail -f /var/log/odoo/odoo-server.log`

#### Error: "Authentication failed via RPC"

**Check:**
1. Verify admin password (default: admin/admin for new DBs)
2. Check if admin user exists
3. Try resetting admin password

**For complete troubleshooting guide, see:** `RPC_API_GUIDE.md`

## 🔒 Security Hardening

### 1. PostgreSQL Security

```sql
-- Restrict template databases from normal users
REVOKE CONNECT ON DATABASE template_blank FROM PUBLIC;
REVOKE CONNECT ON DATABASE template_restaurant FROM PUBLIC;
REVOKE CONNECT ON DATABASE template_ecommerce FROM PUBLIC;
REVOKE CONNECT ON DATABASE template_services FROM PUBLIC;

-- Only allow odoo user
GRANT CONNECT ON DATABASE template_blank TO odoo;
-- Repeat for other templates
```

### 2. Odoo Security

- Change default admin_passwd in odoo.conf
- Disable database manager (list_db = False)
- Use strong passwords
- Enable 2FA for admin users
- Regular security updates

### 3. Firewall

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### 4. Backup Strategy

```bash
# Automated PostgreSQL backup
0 2 * * * pg_dumpall -U postgres | gzip > /backup/postgres-$(date +\%Y\%m\%d).sql.gz

# Odoo filestore backup
0 3 * * * tar -czf /backup/filestore-$(date +\%Y\%m\%d).tar.gz /var/lib/odoo
```

## 📊 Monitoring Setup

### 1. Log Monitoring

```bash
# Monitor Odoo logs
tail -f /var/log/odoo/odoo-server.log

# Monitor Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### 2. Resource Monitoring

Install monitoring tools:

```bash
# htop for system resources
sudo apt-get install htop

# PostgreSQL monitoring
sudo apt-get install pgtop
```

### 3. Uptime Monitoring

Use external monitoring services:
- UptimeRobot
- Pingdom
- StatusCake

## 🚀 Performance Tuning

### PostgreSQL Vacuum

```bash
# Add to crontab
0 4 * * 0 vacuumdb -U postgres -a -z
```

### Odoo Session Cleanup

The module includes automated cron jobs for:
- Subscription expiry checking (daily 2 AM)
- Instance monitoring (hourly)
- User limit checking (daily 3 AM)
- Auto-renewal (daily 1 AM)

## ✅ Verification

### Test Configuration

1. **Test Database Filter:**
   ```bash
   # Access main domain
   curl -I https://example.com
   
   # Access subdomain
   curl -I https://test.example.com
   ```

2. **Test Instance Creation:**
   - Create a test instance via UI
   - Verify subdomain works
   - Check database was created in PostgreSQL

3. **Test Provisioning (Phase 2):**
   - Provision an instance
   - Verify 10-second completion
   - Access instance via subdomain

## 🆘 Troubleshooting

### Database Filter Not Working

```bash
# Check Odoo logs
grep "dbfilter" /var/log/odoo/odoo-server.log

# Verify odoo.conf
grep "dbfilter" /etc/odoo/odoo.conf

# Restart Odoo
sudo systemctl restart odoo
```

### SSL Certificate Issues

```bash
# Renew certificates
sudo certbot renew

# Check certificate
sudo certbot certificates
```

### Performance Issues

```bash
# Check PostgreSQL connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check Odoo workers
ps aux | grep odoo-bin
```

## 📚 Additional Resources

- **RPC_API_GUIDE.md** - Complete RPC API reference and troubleshooting
- [Odoo Documentation](https://www.odoo.com/documentation/18.0/)
- [Odoo External API](https://www.odoo.com/documentation/18.0/developer/reference/external_api.html)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [PostgreSQL Template Databases](https://www.postgresql.org/docs/current/manage-ag-templatedbs.html)
- [Odoo Documentation](https://www.odoo.com/documentation/18.0/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)

## 🤝 Support

For configuration assistance:
- **RPC Issues:** See RPC_API_GUIDE.md for detailed troubleshooting
- Review Odoo logs (`/var/log/odoo/odoo-server.log`)
- Check PostgreSQL logs (`/var/log/postgresql/`)
- Test RPC endpoint with curl commands (see above)
- Review Odoo logs
- Check PostgreSQL logs
- Consult system administrator
- Contact implementation partner
