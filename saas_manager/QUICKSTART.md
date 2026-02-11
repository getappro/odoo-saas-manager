# 🚀 SaaS Manager - Quick Start Guide

## 5-Minute Setup (No Phase 2 implementation)

This guide helps you install and explore the SaaS Manager module structure.

### Prerequisites
- Odoo 18 installed and running
- PostgreSQL database
- Access to Odoo configuration file

### Step 1: Copy Module (30 seconds)

```bash
# Copy the saas_manager folder to your Odoo addons directory
cp -r saas_manager /path/to/odoo/addons/

# Or create a symlink
ln -s /path/to/saas_manager /path/to/odoo/addons/
```

### Step 2: Configure Odoo (1 minute)

Edit your `odoo.conf`:

```ini
[options]
# ESSENTIAL: Enable subdomain-based database routing
dbfilter = ^%h$

# Recommended settings
workers = 4
db_maxconn = 64
proxy_mode = True
```

**Important:** The `dbfilter = ^%h$` setting is critical for multi-DB routing!

### Step 3: Restart Odoo (30 seconds)

```bash
# If using systemd
sudo systemctl restart odoo

# Or if running manually
sudo service odoo restart
```

### Step 4: Install Module (2 minutes)

1. Open Odoo in your browser
2. Go to **Apps** menu
3. Click **Update Apps List**
4. Search for "SaaS Manager"
5. Click **Install**

### Step 5: Configure Base Domain (30 seconds)

After installation:

1. Go to **Settings → Technical → Parameters → System Parameters**
2. Find `saas.base_domain`
3. Change value from `example.com` to your actual domain
4. Save

### Step 6: Create Your First Template via RPC (5-10 minutes)

**Prerequisites:**
- Ensure `web.base.url` is configured (Settings → Technical → Parameters → System Parameters)
- Ensure `admin_passwd` is set in odoo.conf (required for RPC)

**Create Template Database:**

1. **Go to Templates**
   - Menu: **SaaS Manager → Configuration → Templates**
   - View: 4 pre-configured templates (Blank, Restaurant, E-commerce, Services)

2. **Select a Template**
   - Click on "Blank Template" (fastest to create)
   - Or choose "Restaurant Template" for full example

3. **Create Template DB**
   - Click **"Create Template DB"** button
   - **NEW:** This now works via RPC API! (No longer TODO)
   - Watch for notification: "Template Created Successfully"

4. **What Happens (5-10 minutes):**
   - ⏱️ Step 1: Creating PostgreSQL database via RPC (~30 seconds)
   - ⏱️ Step 2: Authenticating to new database (~2 seconds)
   - ⏱️ Step 3: Installing base modules (base, web, mail, portal) (~2-5 minutes)
   - ⏱️ Step 4: Marking template as ready (~1 second)
   - ✅ Template marked as "Ready" automatically

5. **Verify Template Creation:**
   - Check `is_template_ready` field is checked ✓
   - See installed modules in the template record
   - Template database exists in PostgreSQL

**Troubleshooting:**
- **Error "Failed to connect to RPC endpoint":** Check `web.base.url` parameter
- **Error "RPC Error while creating database":** Verify `admin_passwd` in odoo.conf
- **Timeout:** Normal for first template (may take up to 10 minutes)

**See:** `RPC_API_GUIDE.md` for detailed troubleshooting

### Step 7: Explore Other Features (2 minutes)
### Step 6: Explore the Module (2 minutes)

Access the **SaaS Manager** main menu to explore:

#### Templates
- **Menu:** SaaS Manager → Configuration → Templates
- **What to see:** 4 pre-configured templates (Blank, Restaurant, E-commerce, Services)
- **Try:** Click on a template, view its description
- **Note:** "Create Template DB" button shows TODO Phase 2 message

#### Plans
- **Menu:** SaaS Manager → Configuration → Plans
- **What to see:** 3 subscription plans with pricing
- **Try:** Switch between List, Kanban views
- **Note:** Observe user limits, storage limits, prices

#### Instances
- **Menu:** SaaS Manager → Operations → Instances
- **What to create:** A test instance
  - Name: "Demo Instance"
  - Customer: Choose any partner
  - Subdomain: "demo-client"
  - Template: "Blank Template" (or the one you created)
  - Plan: "Professional"
- **Note:** "Provision Instance" button still shows TODO (Phase 2)
  - Template: "Restaurant Template"
  - Plan: "Professional"
- **Note:** "Provision Instance" button shows TODO Phase 2 message

#### Subscriptions
- **Menu:** SaaS Manager → Operations → Subscriptions
- **What to see:** Subscription management interface
- **Try:** Create a subscription for your test instance

## ✅ What Works Now (Phase 1.5 - RPC Implementation)
## What Works Now (Without Phase 2)

✅ **Fully Functional:**
- Module installation
- All menu items
- All views (form, list, kanban)
- Data creation (templates, plans, instances, subscriptions)
- Security groups (User, Manager, Administrator)
- State workflows on instances
- Search and filters
- Data validation
- **✨ NEW: Template database creation via RPC**
- **✨ NEW: Automated module installation**
- **✨ NEW: Template ready verification**

⏳ **Still TODO (Phase 2):**
- Instance provisioning (clone + customize)
- Database neutralization
- Client admin user creation

⏳ **Shows TODO Message (Phase 2 Required):**
- Template database creation
- Instance provisioning
- Database cloning
- Subdomain configuration
- User/storage metrics
- Actual instance access

**Template Cloning:** Already implemented! See `clone_template_db()` method (uses psycopg2)

## Explore the Code

### Key Files to Review

```bash
# Core business logic
saas_manager/models/saas_instance.py    # Provisioning orchestration
saas_manager/models/saas_template.py    # Template management
saas_manager/models/saas_plan.py        # Subscription plans

# Views (Odoo 18 compliant)
saas_manager/views/saas_instance_views.xml
saas_manager/views/saas_template_views.xml

# Security
saas_manager/security/saas_security.xml
saas_manager/security/ir.model.access.csv

# Data
saas_manager/data/saas_template_data.xml
saas_manager/data/saas_plan_data.xml
```

### Look for TODO Comments

All Phase 2 implementation points are marked with `TODO Phase 2`:

```bash
# Find all TODO items
grep -r "TODO Phase 2" saas_manager/models/
```

## Test the Module

### Create Test Data

1. **Create a customer:**
   - Contacts → Create
   - Name: "Test Company"
   - Save

2. **Create a template (NEW - RPC-based):**
   - SaaS Manager → Configuration → Templates
   - Select "Blank Template"
   - Click "Create Template DB"
   - Wait 5-10 minutes
   - Verify `is_template_ready` is checked ✓

3. **Create an instance:**
2. **Create an instance:**
   - SaaS Manager → Operations → Instances → Create
   - Name: "Test Instance"
   - Customer: "Test Company"
   - Subdomain: "testcompany"
   - Template: "Blank Template" (the one you just created)
   - Plan: "Professional"
   - Save

4. **Observe the computed fields:**
   - Domain: `testcompany.example.com` (auto-computed)
   - State: `draft` (initial state)

5. **Try state transitions:**
   - Click "Provision Instance" (still shows TODO message - Phase 2)
   - Template: "Restaurant Template"
   - Plan: "Professional"
   - Save

3. **Observe the computed fields:**
   - Domain: `testcompany.example.com` (auto-computed)
   - State: `draft` (initial state)

4. **Try state transitions:**
   - Click "Provision Instance" (shows TODO message)
   - Manually change state to "Active"
   - Try "Suspend" button
   - Try "Reactivate" button

### Test Template Cloning (Already Implemented!)

**Via Odoo Shell:**
```bash
cd /path/to/odoo
./odoo-bin shell -d your_main_db
```

**Python Code:**
```python
# Get template
template = env['saas.template'].search([('code', '=', 'blank')], limit=1)

# Verify template is ready
print(f"Template Ready: {template.is_template_ready}")

# Clone template (ultra-fast PostgreSQL TEMPLATE)
template.clone_template_db('test_client_db')
# Result: New database created in ~5-10 seconds!

# Verify in PostgreSQL
import subprocess
subprocess.run(['sudo', '-u', 'postgres', 'psql', '-c', '\\l'])
```

### Verify Security

1. **Create test users:**
   - User with "SaaS Manager / User" group (read-only)
   - User with "SaaS Manager / Manager" group (CRUD)
   - User with "SaaS Manager / Administrator" group (full access)

2. **Test permissions:**
   - User can only read instances
   - Manager can create/edit instances but not templates
   - Admin can access everything

## ✅ Next Steps: Remaining Phase 2 Implementation

**What's Already Done:**
- ✅ Template database creation (RPC-based)
- ✅ Module installation (RPC-based)
- ✅ Template cloning (psycopg2)

**What's Still TODO:**

### 1. Instance Customization (`odoorpc` or RPC extension)
## Next Steps: Phase 2 Implementation

To make the module fully functional, implement these TODO functions:

### 1. Database Operations (`psycopg2`)
```python
# saas_manager/models/saas_instance.py
def _clone_template_database(self):
    # Implement PostgreSQL template cloning
    # CREATE DATABASE client1 WITH TEMPLATE template_restaurant
```

### 2. Instance Customization (`odoorpc`)
```python
def _neutralize_database(self):
    # Reset passwords, anonymize demo data
    
def _customize_instance(self):
    # Apply customer branding, company name, logo
    
def _create_client_admin(self):
    # Create admin user with custom credentials
```

### 2. Infrastructure
    # Apply customer branding
    
def _create_client_admin(self):
    # Create admin user with credentials
```

### 3. Infrastructure
```python
def _configure_subdomain(self):
    # Configure DNS and reverse proxy
    # Cloudflare API, Nginx config, etc.
```

### 3. Monitoring
### 4. Monitoring
```python
def _compute_current_users(self):
    # Query instance database for user count
    
def _compute_storage_used(self):
    # Calculate PostgreSQL database size
```

## Troubleshooting

### Module Not Appearing in Apps
```bash
# Check module is in addons path
ls /path/to/odoo/addons/saas_manager

# Check Odoo log for errors
tail -f /var/log/odoo/odoo-server.log

# Update apps list
# Apps → Update Apps List
```

### Installation Fails
```bash
# Check Python syntax
python3 -m py_compile saas_manager/models/*.py

# Check XML syntax
python3 check_module.py

# Review Odoo logs for specific error
```

### Views Not Loading
```bash
# Check XML is valid
python3 << 'EOF'
import xml.etree.ElementTree as ET
ET.parse('saas_manager/views/saas_instance_views.xml')
print("✓ XML is valid")
EOF
```

### Template Creation Fails (RPC Errors)

**Error: "Failed to connect to Odoo RPC endpoint"**
```bash
# Check web.base.url parameter
cd /path/to/odoo
./odoo-bin shell -d your_db
>>> env['ir.config_parameter'].get_param('web.base.url')

# Test RPC endpoint
curl -I http://localhost:8069/jsonrpc

# Verify Odoo is running
sudo systemctl status odoo
```

**Error: "RPC Error while creating database"**
```bash
# Check admin_passwd in odoo.conf
grep admin_passwd /etc/odoo/odoo.conf

# Verify database doesn't already exist
sudo -u postgres psql -c "\l" | grep template_
```

**Error: "Authentication failed via RPC"**
```bash
# Default credentials for new databases: admin/admin
# Try logging in manually:
http://localhost:8069/web?db=template_blank
# Login: admin
# Password: admin
```

**For complete RPC troubleshooting, see:** `RPC_API_GUIDE.md`

## Documentation

- **RPC_API_GUIDE.md** - Complete RPC API reference and troubleshooting
- **README.md** - Complete feature documentation
- **CONFIGURATION.md** - Production setup guide (includes RPC configuration)
## Documentation

- **README.md** - Complete feature documentation
- **CONFIGURATION.md** - Production setup guide
- **IMPLEMENTATION_SUMMARY.md** - Technical overview
- **This file** - Quick start for testing

## Support

For implementation help:
1. **RPC Issues:** See RPC_API_GUIDE.md for detailed troubleshooting
2. Check inline code comments (detailed implementation notes)
3. Review IMPLEMENTATION_SUMMARY.md for technical overview
4. See example implementations in code comments
5. Consult CONFIGURATION.md for infrastructure setup
1. Check inline code comments (detailed TODOs)
2. Review IMPLEMENTATION_SUMMARY.md
3. See example implementations in code comments
4. Consult CONFIGURATION.md for infrastructure setup

## Success Checklist

After following this guide, you should have:

- [x] Module installed successfully
- [x] All menus accessible
- [x] Templates visible (4 items)
- [x] Plans visible (3 items)
- [x] **NEW:** At least one template created via RPC ✨
- [x] **NEW:** Template marked as "Ready" ✨
- [x] Test instance created
- [x] Views working (list, form, kanban)
- [x] Security groups configured
- [x] Understanding of remaining Phase 2 items

**Congratulations! You've successfully set up the SaaS Manager module with RPC-based template creation!**

Next: Implement remaining Phase 2 functions (instance customization, subdomain setup) to enable full provisioning! 🚀
- [x] Templates visible (4 items)
- [x] Plans visible (3 items)
- [x] Test instance created
- [x] Views working (list, form, kanban)
- [x] Security groups configured
- [x] Understanding of TODO Phase 2 items

**Congratulations! You've successfully set up the SaaS Manager module structure.**

Next: Implement Phase 2 functions to enable actual provisioning! 🚀
