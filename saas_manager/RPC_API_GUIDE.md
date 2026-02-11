# RPC API Guide - SaaS Manager

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [RPC Methods Reference](#rpc-methods-reference)
5. [Usage Examples](#usage-examples)
6. [Troubleshooting](#troubleshooting)
7. [Performance](#performance)
8. [Security Best Practices](#security-best-practices)
9. [API Reference](#api-reference)

## 🎯 Overview

The SaaS Manager module uses **Odoo's JSON-RPC API** for template database creation and module installation instead of direct SQL operations or subprocess calls. This approach provides:

- **Better Integration** - Uses Odoo's native API instead of bypassing it
- **Improved Security** - Leverages Odoo's authentication and authorization
- **Error Handling** - Better error messages and debugging capabilities
- **Compatibility** - Works across different Odoo deployment scenarios
- **Maintainability** - Uses stable, documented Odoo APIs

### Why RPC Instead of Direct SQL?

**Previous Approach (subprocess/SQL):**
```python
# ❌ Old approach - direct subprocess
subprocess.run(['odoo-bin', '-d', db_name, '-i', 'base'])
```

**Current Approach (RPC):**
```python
# ✅ New approach - RPC API
response = requests.post(f"{base_url}/jsonrpc", json=payload)
```

**Benefits:**
- No subprocess management issues
- No dependency on file system paths
- Works with containerized Odoo
- Proper error propagation
- Better logging and debugging

## 🏗️ Architecture

### RPC Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Template Creation Flow                   │
└─────────────────────────────────────────────────────────────┘

1. User clicks "Create Template DB" button
              ↓
2. action_create_template_db() called
              ↓
3. Get configuration (web.base.url, admin_passwd)
              ↓
4. _create_template_db_via_rpc()
   └─→ POST /jsonrpc
       └─→ service: "db"
           └─→ method: "create_database"
               └─→ Creates PostgreSQL database
              ↓
5. _install_modules_via_rpc()
   ├─→ POST /jsonrpc (Authentication)
   │   └─→ service: "common", method: "login"
   │       └─→ Returns user_id
   ├─→ For each module:
   │   ├─→ POST /jsonrpc (Search module)
   │   │   └─→ service: "object", method: "execute_kw"
   │   │       └─→ model: "ir.module.module", method: "search"
   │   └─→ POST /jsonrpc (Install module)
   │       └─→ service: "object", method: "execute_kw"
   │           └─→ model: "ir.module.module", method: "button_install"
              ↓
6. Mark template as ready (is_template_ready = True)
              ↓
7. Return success notification
```

### Template Cloning Flow (PostgreSQL)

```
┌─────────────────────────────────────────────────────────────┐
│                  Instance Provisioning Flow                 │
└─────────────────────────────────────────────────────────────┘

1. User provisions new instance
              ↓
2. clone_template_db(new_db_name) called
              ↓
3. Connect to PostgreSQL via psycopg2
              ↓
4. Execute: CREATE DATABASE client1 TEMPLATE template_restaurant
              ↓
5. Database cloned in ~5-10 seconds (ultra-fast)
              ↓
6. Instance ready at subdomain
```

### Security Considerations

1. **Master Password Protection**
   - Required for database creation
   - Stored in odoo.conf (admin_passwd)
   - Never exposed to users
   - Should be strong (20+ characters)

2. **RPC Endpoint Security**
   - Accessible only on configured base_url
   - Can be restricted to localhost
   - Should be behind reverse proxy in production
   - Monitor access logs

3. **Authentication**
   - Each RPC call authenticated
   - Uses admin credentials (admin/admin by default)
   - Credentials can be customized per template

## ⚙️ Configuration

### Required Settings

#### 1. System Parameter: web.base.url

**Location:** Settings → Technical → Parameters → System Parameters

```
Key: web.base.url
Value: http://localhost:8069
       (or https://your-domain.com in production)
```

**Used for:**
- Constructing RPC endpoint URL
- Determining which Odoo instance to connect to

**Verification:**
```bash
# Check if parameter is set
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

#### 2. Master Password: admin_passwd

**Location:** odoo.conf

```ini
[options]
# Master password for database operations
admin_passwd = CHANGE_ME_STRONG_PASSWORD
```

**Security Best Practices:**
- Use strong password (20+ characters)
- Include uppercase, lowercase, numbers, symbols
- Never commit to version control
- Change default password immediately
- Store securely (use secrets management)

**Example strong password:**
```
admin_passwd = K9$mP2#vL8@nQ5&xR7!wT3
```

#### 3. Network Requirements

**Firewall Rules:**
```bash
# Allow Odoo RPC endpoint (internal only)
sudo ufw allow from 127.0.0.1 to any port 8069

# Or for trusted network
sudo ufw allow from 10.0.0.0/8 to any port 8069
```

**Reverse Proxy (Nginx):**
```nginx
# Restrict /jsonrpc to internal IPs only
location /jsonrpc {
    allow 127.0.0.1;
    allow 10.0.0.0/8;
    deny all;
    proxy_pass http://localhost:8069;
}
```

### Testing RPC Endpoint

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
  "result": ["database1", "database2", ...]
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

## 📚 RPC Methods Reference

### Method 1: _create_template_db_via_rpc()

**Purpose:** Create a new PostgreSQL database via Odoo's RPC API

**Location:** `saas_manager/models/saas_template.py` (lines 112-183)

**Signature:**
```python
def _create_template_db_via_rpc(self, base_url, db_name, admin_password='admin'):
    """
    Create a template database via Odoo's jsonrpc2 RPC API.
    
    Args:
        base_url (str): Base URL of the Odoo instance (e.g., 'http://localhost:8069')
        db_name (str): Name of the database to create
        admin_password (str): Master password for database operations
    
    Returns:
        dict: Response from RPC call
    
    Raises:
        UserError: If RPC call fails
    """
```

**RPC Endpoint:** `/jsonrpc`

**Service:** `db`

**Method:** `create_database`

**Parameters:**
1. `admin_password` - Master password from odoo.conf
2. `db_name` - Name of the new database
3. `demo` - Boolean (False = no demo data)
4. `lang` - Language code (e.g., 'en_US')
5. `user_password` - Admin password for the new database (default: 'admin')

**Timeout:** 600 seconds (10 minutes)

**Example Payload:**
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "service": "db",
    "method": "create_database",
    "args": [
      "master_password_here",
      "template_restaurant",
      false,
      "en_US",
      "admin"
    ]
  },
  "id": 1
}
```

**Success Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": true
}
```

**Error Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": 200,
    "message": "Odoo Server Error",
    "data": {
      "message": "Database creation error: ...",
      "debug": "..."
    }
  }
}
```

### Method 2: _install_modules_via_rpc()

**Purpose:** Install Odoo modules in an existing database via RPC

**Location:** `saas_manager/models/saas_template.py` (lines 185-316)

**Signature:**
```python
def _install_modules_via_rpc(self, base_url, db_name, modules_to_install, 
                             admin_login='admin', admin_password='admin'):
    """
    Install modules in the database via RPC API.
    
    Args:
        base_url (str): Base URL of the Odoo instance
        db_name (str): Database name
        modules_to_install (list): List of module names to install
        admin_login (str): Admin login username
        admin_password (str): Admin password
    
    Returns:
        dict: Response from RPC call
    
    Raises:
        UserError: If module installation fails
    """
```

**Process:**
1. **Authenticate** via `common.login`
2. **Search** for modules via `ir.module.module.search`
3. **Install** modules via `ir.module.module.button_install`

**Step 1: Authentication**

**Payload:**
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "service": "common",
    "method": "login",
    "args": ["template_restaurant", "admin", "admin"]
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": 2  // user_id
}
```

**Step 2: Search for Module**

**Payload:**
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "service": "object",
    "method": "execute_kw",
    "args": [
      "template_restaurant",
      2,
      "admin",
      "ir.module.module",
      "search",
      [[["name", "=", "mail"]]]
    ]
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": [42]  // module_ids
}
```

**Step 3: Install Module**

**Payload:**
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "service": "object",
    "method": "execute_kw",
    "args": [
      "template_restaurant",
      2,
      "admin",
      "ir.module.module",
      "button_install",
      [[42]]
    ]
  },
  "id": 1
}
```

**Default Modules Installed:**
```python
modules_to_install = ['base', 'web', 'mail', 'portal']
```

### Method 3: action_create_template_db()

**Purpose:** Main orchestration method for template creation

**Location:** `saas_manager/models/saas_template.py` (lines 318-389)

**Signature:**
```python
def action_create_template_db(self):
    """
    Create the PostgreSQL template database and initialize it via RPC.
    
    Steps:
    1. Create database via RPC jsonrpc2 API
    2. Authenticate to the database
    3. Install base modules via RPC
    4. Mark template as ready
    
    Returns:
        dict: Notification action
    
    Raises:
        UserError: If database creation fails
    """
```

**Workflow:**
1. Get `web.base.url` from system parameters
2. Get `admin_passwd` from odoo.conf
3. Call `_create_template_db_via_rpc()`
4. Call `_install_modules_via_rpc()` with base modules
5. Set `is_template_ready = True`
6. Return success notification

**Notification Response:**
```python
{
    'type': 'ir.actions.client',
    'tag': 'display_notification',
    'params': {
        'title': 'Template Created Successfully',
        'message': 'Template database "template_restaurant" has been created and initialized via RPC.',
        'type': 'success',
        'sticky': False,
    }
}
```

### Method 4: clone_template_db()

**Purpose:** Clone template database for fast instance provisioning (uses psycopg2, not RPC)

**Location:** `saas_manager/models/saas_template.py` (lines 422-515)

**Signature:**
```python
def clone_template_db(self, new_db_name):
    """
    Clone the PostgreSQL template database using PostgreSQL TEMPLATE feature.
    
    Args:
        new_db_name (str): Name of the new database to create
    
    Returns:
        bool: True if successful
    
    Raises:
        UserError: If cloning fails
    """
```

**Technology:** Direct PostgreSQL connection via psycopg2

**SQL Command:**
```sql
CREATE DATABASE client1 TEMPLATE template_restaurant WITH OWNER odoo;
```

**Performance:** ~5-10 seconds (ultra-fast)

**Why psycopg2 instead of RPC:**
- PostgreSQL template cloning is not available via Odoo RPC
- Direct SQL is the only way to leverage PostgreSQL's TEMPLATE feature
- Much faster than copying database via Odoo API
- Standard PostgreSQL operation

## 💡 Usage Examples

### Example 1: Creating a Template via UI

**Steps:**
1. Navigate to **SaaS Manager → Configuration → Templates**
2. Select a template (e.g., "Restaurant Template")
3. Click **"Create Template DB"** button
4. Wait 5-10 minutes for completion (depends on modules)
5. Template will be marked as "Ready" ✓

**What Happens Behind the Scenes:**
```python
# User clicks button → triggers action_create_template_db()
template = env['saas.template'].browse(1)
result = template.action_create_template_db()

# Step 1: Create database
template._create_template_db_via_rpc(
    base_url='http://localhost:8069',
    db_name='template_restaurant',
    admin_password='master_pwd_from_conf'
)

# Step 2: Install modules
template._install_modules_via_rpc(
    base_url='http://localhost:8069',
    db_name='template_restaurant',
    modules_to_install=['base', 'web', 'mail', 'portal'],
    admin_login='admin',
    admin_password='admin'
)

# Step 3: Mark as ready
template.is_template_ready = True
```

### Example 2: Creating a Template via Code

**Odoo Shell:**
```bash
cd /path/to/odoo
./odoo-bin shell -d your_main_db
```

**Python Code:**
```python
# Get template record
template = env['saas.template'].search([('code', '=', 'restaurant')], limit=1)

# Create template database
result = template.action_create_template_db()
print(result)

# Check status
print(f"Template Ready: {template.is_template_ready}")
print(f"Template DB: {template.template_db}")
```

### Example 3: Creating Template with Custom Modules

**Python Code:**
```python
template = env['saas.template'].browse(1)

# Create database
template._create_template_db_via_rpc(
    base_url='http://localhost:8069',
    db_name='template_custom',
    admin_password='master_password'
)

# Install custom modules
template._install_modules_via_rpc(
    base_url='http://localhost:8069',
    db_name='template_custom',
    modules_to_install=['base', 'web', 'sale', 'stock', 'purchase', 'account'],
    admin_login='admin',
    admin_password='admin'
)

template.write({'is_template_ready': True})
```

### Example 4: Cloning a Template (PostgreSQL)

**Python Code:**
```python
# Get template
template = env['saas.template'].search([('code', '=', 'restaurant')], limit=1)

# Clone to new database
success = template.clone_template_db('client_acme_corp')

# Result: New database 'client_acme_corp' created in ~5 seconds
```

**Manual PostgreSQL Clone:**
```sql
-- Connect to PostgreSQL
psql -U odoo -d postgres

-- Clone template
CREATE DATABASE client_demo TEMPLATE template_restaurant WITH OWNER odoo;

-- Verify
\l
```

## 🔧 Troubleshooting

### Error: "Failed to connect to Odoo RPC endpoint"

**Symptoms:**
```
UserError: Failed to connect to Odoo RPC endpoint.

URL: http://localhost:8069

Error: HTTPConnectionPool(host='localhost', port=8069): Max retries exceeded
```

**Causes:**
1. Odoo is not running
2. Wrong base URL configured
3. Firewall blocking connection
4. Network issues

**Solutions:**

**1. Check Odoo is running:**
```bash
sudo systemctl status odoo
# or
ps aux | grep odoo-bin
```

**2. Verify base URL:**
```bash
# Check system parameter
cd /path/to/odoo
./odoo-bin shell -d your_db

env['ir.config_parameter'].get_param('web.base.url')
# Should return: 'http://localhost:8069' or your actual URL
```

**3. Test RPC endpoint:**
```bash
curl -I http://localhost:8069/jsonrpc
# Should return: HTTP/1.1 200 OK
```

**4. Check firewall:**
```bash
sudo ufw status
# Ensure port 8069 is allowed
```

### Error: "RPC Error while creating database"

**Symptoms:**
```
UserError: RPC Error while creating database.

Error: FATAL: password authentication failed for user "odoo"
```

**Causes:**
1. Incorrect master password
2. Database already exists
3. PostgreSQL permission issues

**Solutions:**

**1. Verify master password:**
```bash
grep admin_passwd /etc/odoo/odoo.conf
```

**2. Check if database exists:**
```bash
sudo -u postgres psql -c "\l" | grep template_restaurant
```

**3. Verify PostgreSQL permissions:**
```bash
sudo -u postgres psql
\du odoo
# Should show CREATEDB permission
```

**4. Test database creation manually:**
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

### Error: "Authentication failed via RPC"

**Symptoms:**
```
UserError: Authentication failed via RPC.

Error: Login failed
```

**Causes:**
1. Wrong admin credentials
2. Admin user doesn't exist
3. Database not initialized properly

**Solutions:**

**1. Verify admin password:**
```bash
# For newly created databases, default is admin/admin
# Try logging in via web interface:
http://localhost:8069/web?db=template_restaurant
# Login: admin
# Password: admin
```

**2. Reset admin password:**
```bash
cd /path/to/odoo
./odoo-bin shell -d template_restaurant

# Reset password
admin_user = env['res.users'].search([('login', '=', 'admin')], limit=1)
admin_user.password = 'admin'
env.cr.commit()
```

**3. Check user exists:**
```bash
sudo -u postgres psql template_restaurant
SELECT login FROM res_users WHERE login = 'admin';
```

### Error: "Module not found"

**Symptoms:**
```
WARNING: Module mail not found
```

**Causes:**
1. Module doesn't exist in addons path
2. Typo in module name
3. Module not available in Odoo version

**Solutions:**

**1. Check module exists:**
```bash
# Find module
find /path/to/odoo/addons -name "__manifest__.py" -path "*/mail/*"
```

**2. Verify module name:**
```bash
cd /path/to/odoo
./odoo-bin shell -d template_restaurant

# Search module
env['ir.module.module'].search([('name', '=', 'mail')])
```

**3. Update apps list:**
```python
env['ir.module.module'].update_list()
```

### Error: "Database already exists"

**Symptoms:**
```
RPC Error: Database creation error: database "template_restaurant" already exists
```

**Solutions:**

**1. Drop existing database:**
```bash
sudo -u postgres psql
DROP DATABASE template_restaurant;
```

**2. Or rename in template record:**
```python
template = env['saas.template'].browse(1)
template.template_db = 'template_restaurant_v2'
```

### Error: "Timeout during module installation"

**Symptoms:**
```
ReadTimeout: HTTPSConnectionPool(host='localhost', port=8069): Read timed out
```

**Solutions:**

**1. Increase timeout in code:**
```python
# Already set to 600 seconds (10 minutes)
# If still timing out, modules might be too heavy
```

**2. Install modules one by one:**
```python
template = env['saas.template'].browse(1)

# Install base modules first
template._install_modules_via_rpc(
    base_url, db_name, ['base', 'web'], admin_login='admin', admin_password='admin'
)

# Then install others
template._install_modules_via_rpc(
    base_url, db_name, ['mail', 'portal'], admin_login='admin', admin_password='admin'
)
```

**3. Check Odoo logs:**
```bash
tail -f /var/log/odoo/odoo-server.log
# Look for module installation errors
```

## ⚡ Performance

### Database Creation

**Timeline:**
- RPC connection: ~0.5 seconds
- Database creation: ~30 seconds
- Module installation: ~2-5 minutes (depends on modules)
- **Total: ~5-10 minutes**

**Benchmark:**
```
Module Installation Times (approximate):
- base: ~30 seconds
- web: ~45 seconds  
- mail: ~60 seconds
- portal: ~30 seconds
- sale: ~90 seconds
- stock: ~120 seconds
- account: ~150 seconds
```

**Optimization Tips:**
1. Install only necessary modules in template
2. Add custom modules after template creation
3. Use SSD storage for PostgreSQL
4. Increase PostgreSQL shared_buffers

### Template Cloning

**Performance:**
- PostgreSQL TEMPLATE clone: **~5-10 seconds**
- Traditional database copy: ~120+ seconds
- **Speed improvement: 12x faster**

**Benchmark:**
```bash
# Test template clone speed
time sudo -u postgres psql -c "CREATE DATABASE test_clone TEMPLATE template_restaurant"

# Typical results:
# real    0m8.234s
# user    0m0.004s
# sys     0m0.008s
```

**Factors Affecting Speed:**
- Database size (larger = slower)
- Disk I/O speed (SSD much faster)
- PostgreSQL configuration
- Server load

### Comparison: RPC vs Subprocess

| Method | Pros | Cons | Speed |
|--------|------|------|-------|
| **RPC API** | ✅ Stable API<br>✅ Better errors<br>✅ No subprocess<br>✅ Works remotely | ⚠️ Network overhead | 5-10 min |
| **Subprocess** | ✅ Direct control | ❌ Path dependencies<br>❌ Environment issues<br>❌ Poor errors | 5-10 min |

**Winner:** RPC API (better reliability and maintainability)

## 🔒 Security Best Practices

### 1. Master Password Security

**❌ BAD:**
```ini
# odoo.conf
admin_passwd = admin
```

**✅ GOOD:**
```ini
# odoo.conf
admin_passwd = K9$mP2#vL8@nQ5&xR7!wT3yH6^bN4!mL5
```

**Best Practices:**
- Use password manager to generate strong passwords
- Minimum 20 characters
- Mix uppercase, lowercase, numbers, symbols
- Rotate password quarterly
- Never commit to version control
- Use environment variables in production

**Environment Variable Approach:**
```bash
# /etc/systemd/system/odoo.service
[Service]
Environment="ADMIN_PASSWD=K9$mP2#vL8@nQ5&xR7!wT3"
ExecStart=/usr/bin/odoo --admin-passwd=${ADMIN_PASSWD}
```

### 2. RPC Endpoint Security

**Network Restrictions:**
```nginx
# Nginx configuration
location /jsonrpc {
    # Allow only from localhost
    allow 127.0.0.1;
    deny all;
    
    proxy_pass http://localhost:8069;
}
```

**Firewall Rules:**
```bash
# UFW firewall
sudo ufw deny 8069/tcp
sudo ufw allow from 127.0.0.1 to any port 8069
```

**IP Whitelist:**
```nginx
# Allow specific IPs only
location /jsonrpc {
    allow 10.0.0.0/8;     # Internal network
    allow 192.168.1.100;   # Admin workstation
    deny all;
    
    proxy_pass http://localhost:8069;
}
```

### 3. Database Credentials

**Template Admin Password:**
```python
# Change default admin password after creation
template = env['saas.template'].browse(1)
template._create_template_db_via_rpc(
    base_url, 
    'template_restaurant',
    master_pwd,
    user_password='StrongPass123!'  # Not 'admin'
)
```

**Password Policy:**
```python
# Enforce strong passwords for template admins
def _create_template_db_via_rpc(self, base_url, db_name, admin_password, user_password=None):
    if not user_password:
        # Generate random password
        import secrets
        user_password = secrets.token_urlsafe(16)
        _logger.info(f"Generated admin password: {user_password}")
    
    # ... rest of code
```

### 4. Audit Logging

**Log all RPC calls:**
```python
def _create_template_db_via_rpc(self, base_url, db_name, admin_password):
    _logger.info(f"RPC: Creating database {db_name} from {self.env.user.login}")
    _logger.info(f"RPC: Base URL: {base_url}")
    
    # ... RPC call ...
    
    _logger.info(f"RPC: Database {db_name} created successfully")
```

**Monitor logs:**
```bash
# Watch for RPC activity
tail -f /var/log/odoo/odoo-server.log | grep "RPC:"

# Check for failed attempts
grep "RPC Error" /var/log/odoo/odoo-server.log
```

### 5. Access Control

**Restrict template creation:**
```xml
<!-- Only administrators can create templates -->
<record id="saas_template_admin_rule" model="ir.rule">
    <field name="name">SaaS Template: Admin only</field>
    <field name="model_id" ref="model_saas_template"/>
    <field name="groups" eval="[(4, ref('saas_manager.group_saas_administrator'))]"/>
    <field name="perm_create" eval="True"/>
    <field name="perm_write" eval="True"/>
    <field name="perm_unlink" eval="True"/>
</record>
```

### 6. Template Database Protection

**PostgreSQL Security:**
```sql
-- Revoke public access to templates
REVOKE CONNECT ON DATABASE template_restaurant FROM PUBLIC;
REVOKE CONNECT ON DATABASE template_ecommerce FROM PUBLIC;
REVOKE CONNECT ON DATABASE template_services FROM PUBLIC;

-- Only allow odoo user
GRANT CONNECT ON DATABASE template_restaurant TO odoo;
```

**Mark as template:**
```sql
-- Prevent accidental modifications
UPDATE pg_database SET datistemplate = TRUE 
WHERE datname LIKE 'template_%';
```

## 📖 API Reference

### Complete RPC Services Used

#### 1. Database Service (`db`)

**List databases:**
```json
{
  "service": "db",
  "method": "list",
  "args": []
}
```

**Create database:**
```json
{
  "service": "db",
  "method": "create_database",
  "args": [
    "master_password",
    "database_name",
    false,              // demo data
    "en_US",           // language
    "admin_password"   // admin password
  ]
}
```

**Drop database:**
```json
{
  "service": "db",
  "method": "drop",
  "args": [
    "master_password",
    "database_name"
  ]
}
```

**Duplicate database:**
```json
{
  "service": "db",
  "method": "duplicate_database",
  "args": [
    "master_password",
    "source_db",
    "target_db"
  ]
}
```

#### 2. Common Service (`common`)

**Get version:**
```json
{
  "service": "common",
  "method": "version",
  "args": []
}
```

**Login (authenticate):**
```json
{
  "service": "common",
  "method": "login",
  "args": [
    "database_name",
    "username",
    "password"
  ]
}
```

**Authenticate (with API key):**
```json
{
  "service": "common",
  "method": "authenticate",
  "args": [
    "database_name",
    "username",
    "api_key",
    {}
  ]
}
```

#### 3. Object Service (`object`)

**Execute method:**
```json
{
  "service": "object",
  "method": "execute_kw",
  "args": [
    "database_name",
    user_id,           // from login
    "password",
    "model.name",      // e.g., "ir.module.module"
    "method_name",     // e.g., "search", "write", "create"
    [...],            // positional args
    {...}             // keyword args (optional)
  ]
}
```

**Search records:**
```json
{
  "service": "object",
  "method": "execute_kw",
  "args": [
    "database_name",
    user_id,
    "password",
    "ir.module.module",
    "search",
    [[["name", "=", "sale"]]]
  ]
}
```

**Read records:**
```json
{
  "service": "object",
  "method": "execute_kw",
  "args": [
    "database_name",
    user_id,
    "password",
    "ir.module.module",
    "read",
    [[module_id]],
    {"fields": ["name", "state"]}
  ]
}
```

**Install module:**
```json
{
  "service": "object",
  "method": "execute_kw",
  "args": [
    "database_name",
    user_id,
    "password",
    "ir.module.module",
    "button_install",
    [[module_id]]
  ]
}
```

### HTTP Request Format

**Headers:**
```http
POST /jsonrpc HTTP/1.1
Host: localhost:8069
Content-Type: application/json
Content-Length: 234
```

**Body:**
```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "service": "service_name",
    "method": "method_name",
    "args": [...]
  },
  "id": 1
}
```

**Response (Success):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": ...
}
```

**Response (Error):**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": 200,
    "message": "Odoo Server Error",
    "data": {
      "name": "...",
      "debug": "...",
      "message": "...",
      "arguments": [...],
      "context": {...}
    }
  }
}
```

### Python Requests Example

```python
import requests
import json

def call_rpc(url, service, method, *args):
    """Generic RPC caller"""
    payload = {
        'jsonrpc': '2.0',
        'method': 'call',
        'params': {
            'service': service,
            'method': method,
            'args': list(args)
        },
        'id': 1
    }
    
    response = requests.post(
        f"{url}/jsonrpc",
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )
    
    response.raise_for_status()
    result = response.json()
    
    if 'error' in result:
        raise Exception(result['error'])
    
    return result.get('result')

# Example usage
base_url = 'http://localhost:8069'

# List databases
databases = call_rpc(base_url, 'db', 'list')
print(f"Databases: {databases}")

# Login
user_id = call_rpc(base_url, 'common', 'login', 'mydb', 'admin', 'admin')
print(f"User ID: {user_id}")

# Search modules
module_ids = call_rpc(
    base_url, 'object', 'execute_kw',
    'mydb', user_id, 'admin',
    'ir.module.module', 'search',
    [[['name', '=', 'sale']]]
)
print(f"Module IDs: {module_ids}")
```

## 🎯 Next Steps

### For Users
1. Configure `web.base.url` and `admin_passwd`
2. Create your first template via UI
3. Clone template to provision instances
4. Monitor template usage and performance

### For Developers
1. Review RPC method implementations
2. Understand error handling patterns
3. Extend with custom module installation
4. Add monitoring and alerting

### For System Administrators
1. Secure RPC endpoint (firewall, nginx)
2. Monitor RPC logs for anomalies
3. Set up database backups
4. Configure PostgreSQL for optimal performance

## 📚 Additional Resources

- [Odoo External API Documentation](https://www.odoo.com/documentation/18.0/developer/reference/external_api.html)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [PostgreSQL Template Databases](https://www.postgresql.org/docs/current/manage-ag-templatedbs.html)
- [Python Requests Library](https://docs.python-requests.org/)

---

**Last Updated:** December 2024  
**Odoo Version:** 18.0  
**Module:** saas_manager  
**Author:** SaaS Manager Development Team
