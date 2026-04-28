# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
SaaS Instance Model
===================
Instance client avec provisioning automatisé.
Client instance with automated provisioning.
"""

import logging
import secrets
import string
import requests
import time
import jwt
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SaaSInstance(models.Model):
    """
    SaaS Instance - Core Provisioning System
    
    Représente une instance client avec provisioning automatisé via
    clonage PostgreSQL des templates.
    
    Represents a client instance with automated provisioning via
    PostgreSQL template cloning.
    """
    _name = 'saas.instance'
    _description = 'SaaS Instance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Instance Name',
        required=True,
        tracking=True,
        help="Name of the instance"
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        ondelete='restrict',
        default=lambda self: self.env.user.partner_id,
        help="Customer owning this instance"
    )
    database_name = fields.Char(
        string='Database Name',
        required=True,
        tracking=True,
        help="PostgreSQL database name"
    )
    subdomain = fields.Char(
        string='Subdomain',
        required=True,
        tracking=True,
        help="Subdomain (e.g., 'client1')"
    )
    domain = fields.Char(
        string='Full Domain',
        compute='_compute_domain',
        store=True,
        help="Full domain (e.g., 'client1.example.com')"
    )
    protocol = fields.Selection([
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
    ], string='Protocol', default='https', required=True,
        help="Protocol to use when accessing the instance (HTTP for development, HTTPS for production)")
    template_id = fields.Many2one(
        'saas.template',
        string='Template',
        required=True,
        tracking=True,
        ondelete='restrict',
        help="Template used for this instance"
    )
    server_id = fields.Many2one(
        'saas.server',
        string='Server',
        required=True,
        tracking=True,
        ondelete='restrict',
        domain="[('state', '=', 'active'), ('available_capacity', '>', 0)]",
        default=lambda self: self._get_default_server(),
        help="Server hosting this instance"
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('provisioning', 'Provisioning'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ], string='State', default='draft', required=True, tracking=True)
    stage_id = fields.Many2one(
        'saas.instance.stage',
        string='Stage',
        tracking=True,
        ondelete='restrict',
        # default intentionally not set to avoid queries during module init
        group_expand='_read_group_stage_ids',
        domain=[('active', '=', True)],
        index=True,
    )

    admin_login = fields.Char(
        string='Admin Login',
        tracking=True,
        help="Administrator login"
    )
    admin_password = fields.Char(
        string='Admin Password',
        help="Administrator password (stored encrypted in production)"
    )
    agent_secret = fields.Char(
        string='Agent Secret',
        help="Shared secret with saas_agent for JWT signatures"
    )
    agent_impersonate_login = fields.Char(
        string='SSO Login',
        help="Login utilisé pour l'impersonation par défaut"
    )

    # User Limit Management
    user_limit = fields.Integer(
        string='User Limit',
        #compute='_compute_user_limit',
        store=True,
        readonly=False,
        tracking=True,
        help="Maximum number of users allowed (from plan)"
    )
    current_users = fields.Integer(
        string='Current Users',
        compute='_compute_current_users',
        store=False,
        help="Current number of active users in instance (fetched via RPC)"
    )
    users_percentage = fields.Float(
        string='Users Usage %',
        compute='_compute_users_percentage',
        store=False,
        help="Percentage of user limit used"
    )
    last_sync_date = fields.Datetime(
        string='Last User Sync',
        readonly=True,
        help="Last time user limit was synced to instance"
    )
    storage_used = fields.Float(
        string='Storage Used (GB)',
        compute='_compute_storage_used',
        help="Storage used in GB"
    )
    activation_date = fields.Datetime(
        string='Activation Date',
        tracking=True,
        help="Date when instance was activated"
    )
    expiration_date = fields.Datetime(
        string='Expiration Date',
        tracking=True,
        help="Date when instance will expire"
    )
    version = fields.Char(
        string='Odoo Version',
        default='18.0',
        help="Odoo version"
    )
    notes = fields.Text(
        string='Notes',
        help="Internal notes"
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    color = fields.Integer(
        string='Color Index',
        help="Color for kanban view"
    )

    _sql_constraints = [
        ('database_name_unique', 'UNIQUE(database_name) WHERE state != \'draft\'', 'Database name must be unique!'),
        ('subdomain_unique', 'UNIQUE(subdomain) WHERE state != \'draft\'', 'Subdomain must be unique!'),
    ]

    @api.depends('subdomain')
    def _compute_domain(self):
        """
        Calcule le domaine complet depuis le sous-domaine.
        Compute full domain from subdomain.
        """
        base_domain = self.env['ir.config_parameter'].sudo().get_param(
            'saas.base_domain', 'example.com'
        )
        for instance in self:
            if instance.subdomain:
                instance.domain = f"{instance.subdomain}.{base_domain}"
            else:
                instance.domain = False

    def _get_default_server(self):
        """
        Obtenir le serveur par défaut avec le plus de capacité disponible.
        Get default server with most available capacity.
        """
        Server = self.env['saas.server']
        try:
            return Server.get_available_server(min_capacity_percent=10)
        except UserError:
            # If no server with 10% capacity, try to get any active server
            return Server.search([('state', '=', 'active')], limit=1)

    @api.model
    def _stage_for_state(self, state):
        Stage = self.env['saas.instance.stage']
        try:
            if hasattr(Stage, '_table_exists') and not Stage._table_exists():
                return Stage.browse()
            return Stage.search([('state', '=', state)], order='sequence, id', limit=1)
        except Exception:
            return Stage.browse()

    @api.model
    def _default_stage_id(self):
        Stage = self.env['saas.instance.stage']
        try:
            if hasattr(Stage, '_table_exists') and not Stage._table_exists():
                return False
            stage = self._stage_for_state('draft')
            if not stage:
                stage = Stage.search([], order='sequence, id', limit=1)
            return stage.id
        except Exception:
            return False

    @api.model
    def _read_group_stage_ids(self, stages, domain, order=None):
        order = order or 'sequence, id'
        return stages.search([], order=order)

    #@api.depends('plan_id', 'plan_id.user_limit')
    #def _compute_user_limit(self):
    #    """Get user limit from plan"""
    #    for instance in self:
    #        if instance.plan_id and hasattr(instance.plan_id, 'user_limit'):
    #            instance.user_limit = instance.plan_id.user_limit
    #        else:
    #            instance.user_limit = 10  # Default limit

    def _compute_current_users(self):
        """
        Fetch current user count from instance via RPC.
        """
        for instance in self:
            if instance.state in ('active', 'suspended') and instance.domain:
                instance.current_users = instance._get_users_count_from_instance()
            else:
                instance.current_users = 0

    def _compute_storage_used(self):
        """
        Calcule l'espace disque utilisé.
        Compute storage used.
        
        TODO Phase 2: Query PostgreSQL database size
        """
        for instance in self:
            # Placeholder - TODO Phase 2: Query database size
            instance.storage_used = 0.0

    @api.depends('current_users', 'user_limit')
    def _compute_users_percentage(self):
        """Calculate usage percentage"""
        for instance in self:
            if instance.user_limit > 0:
                instance.users_percentage = (instance.current_users / instance.user_limit) * 100
            else:
                instance.users_percentage = 0.0

    @api.model
    def _generate_random_password(self, length=16):
        """
        Génère un mot de passe aléatoire sécurisé.
        Generate a secure random password.
        
        Args:
            length (int): Password length
            
        Returns:
            str: Random password
        """
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password

    @api.constrains('subdomain')
    def _check_subdomain(self):
        """
        Valider le format du sous-domaine.
        Validate subdomain format.
        """
        for instance in self:
            if instance.subdomain:
                # Only lowercase alphanumeric and hyphens
                if not all(c.isalnum() or c == '-' for c in instance.subdomain):
                    raise ValidationError(_(
                        'Subdomain can only contain lowercase letters, numbers, and hyphens.'
                    ))
                if not instance.subdomain[0].isalnum() or not instance.subdomain[-1].isalnum():
                    raise ValidationError(_(
                        'Subdomain must start and end with a letter or number.'
                    ))

    def action_provision_instance(self):
        """
        Provisionner l'instance complète (orchestration).
        Provision the complete instance (orchestration).
        
        Workflow:
        1. Valider les prérequis
        2. Cloner la base de données template
        3. Neutraliser les données sensibles
        4. Personnaliser l'instance
        5. Créer l'administrateur client
        6. Configurer le sous-domaine
        7. Activer l'instance
        """
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Only draft instances can be provisioned.'))
        
        if not self.template_id.is_template_ready:
            raise UserError(_('Template %s is not ready for cloning.') % self.template_id.name)
        
        # Validate server state
        if self.server_id.state != 'active':
            raise UserError(
                _("Cannot provision instance on server '%s'.\n\n"
                  "Server state is '%s'. Server must be 'active' to provision instances.\n\n"
                  "Please activate the server or select a different server.") % (self.server_id.name, self.server_id.state)
            )
        
        # Validate server capacity
        if self.server_id.available_capacity < 10:
            raise UserError(
                _("Cannot provision instance on server '%s'.\n\n"
                  "Server has only %.1f%% capacity available. Minimum 10%% required.\n\n"
                  "Please select a different server or increase max instances on this server.") % (self.server_id.name, self.server_id.available_capacity)
            )
        
        try:
            # Update state to provisioning
            self.write({'state': 'provisioning'})
            self.env.cr.commit()  # Commit state change
            
            _logger.info(f"Starting provisioning for instance: {self.name}")
            
            # Step 1: Clone template database (~5s)
            self._clone_template_database()
            
            # Step 2: Neutralize sensitive data (~2s)
            self._neutralize_database()
            
            # Step 3: Customize instance (~2s)
            self._customize_instance()
            
            # Step 4: Create client admin (~1s)
            self._create_client_admin()

            # Step 4bis: Push agent secret for JWT (best effort)
            self._ensure_agent_secret()
            self._push_agent_secret_to_instance()

            # Step 4ter: Install l10n module based on country (best effort)
            self._install_l10n_module()

            # Step 5: Configure subdomain (~1s)
            self._configure_subdomain()
            
            # Step 6: Activate instance
            self.write({
                'state': 'active',
                'activation_date': fields.Datetime.now(),
            })
            
            _logger.info(f"Instance {self.name} provisioned successfully")

            # Step 7: Sync user limit to instance
            if self.user_limit:
                if self._send_user_limit_to_instance():
                    self.write({'last_sync_date': fields.Datetime.now()})

            # Step 8: Send provisioning email to customer
            self._send_provisioning_email()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Instance Provisioned'),
                    'message': _('Instance %s is now active at %s') % (self.name, self.domain),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Provisioning failed for {self.name}: {str(e)}")
            self.write({'state': 'draft'})
            raise UserError(_('Provisioning failed: %s') % str(e))

    def _clone_template_database(self):
        """
        Cloner la base de données template PostgreSQL.
        Clone the PostgreSQL template database.
        
        TODO Phase 2: Implement with psycopg2
        
        Example implementation:
            import psycopg2
            
            # Connect to PostgreSQL
            conn = psycopg2.connect(
                dbname='postgres',
                user=config.get('db_user'),
                password=config.get('db_password'),
                host=config.get('db_host'),
                port=config.get('db_port')
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            # Clone template
            template_db = self.template_id.template_db
            target_db = self.database_name
            
            cursor.execute(f"CREATE DATABASE {target_db} WITH TEMPLATE {template_db}")
            cursor.close()
            conn.close()
            
            _logger.info(f"Database {target_db} cloned from {template_db}")
        """
        # Validate that template and instance are on the same server
        if self.template_id.server_id != self.server_id:
            raise UserError(
                _("Template and instance must be on the same server.\n\n"
                  "Template '%s' is on server '%s'\n"
                  "Instance '%s' is on server '%s'\n\n"
                  "Please select a template on the same server or change the instance server.") % (
                      self.template_id.name, self.template_id.server_id.name,
                      self.name, self.server_id.name
                  )
            )
        
        _logger.info(f"Cloning template {self.template_id.template_db} to {self.database_name} on server {self.server_id.name}")
        
        # Call template's clone method which uses server's DB configuration
        self.template_id.clone_template_db(self.database_name)

    def _neutralize_database(self):
        """
        Neutraliser les données sensibles du template cloné.
        Neutralize sensitive data from cloned template.
        
        TODO Phase 2: Implement with odoorpc
        
        Example implementation:
            import odoorpc
            
            # Connect to instance database
            odoo = odoorpc.ODOO(
                host=config.get('odoo_host'),
                port=config.get('odoo_port'),
                protocol='jsonrpc+ssl'
            )
            
            # Login as superuser
            odoo.login(self.database_name, 'admin', 'admin')
            
            # Neutralize data
            User = odoo.env['res.users']
            Partner = odoo.env['res.partner']
            Company = odoo.env['res.company']
            
            # Reset admin password
            admin_user = User.browse(2)
            User.write([admin_user], {'password': 'admin'})
            
            # Clear sensitive company data
            companies = Company.search([])
            Company.write(companies, {
                'vat': False,
                'company_registry': False,
                'email': False,
                'phone': False,
            })
            
            # Anonymize demo users
            demo_users = User.search([('id', '>', 2)])
            for user_id in demo_users:
                User.write([user_id], {
                    'email': f'demo.user{user_id}@example.com',
                    'password': 'demo',
                })
            
            _logger.info(f"Database {self.database_name} neutralized")
        """
        _logger.info(f"TODO Phase 2: Neutralize database {self.database_name}")
        # Placeholder - actual implementation in Phase 2

    def _customize_instance(self):
        _logger.info(f"Customizing instance {self.database_name}")
        # Phase 2: customize company name, logo, etc. via RPC

    def _install_l10n_module(self):
        """Installe le module l10n correspondant au pays saas_country_id via RPC.

        Mapping country.code → l10n module name. Non-bloquant : les erreurs
        sont loggées mais ne font pas échouer le provisioning.
        """
        self.ensure_one()

        L10N_MAP = {
            'MA': 'l10n_ma',
            'SN': 'l10n_sn',
            'FR': 'l10n_fr',
            'BE': 'l10n_be',
            'DZ': 'l10n_dz',
            'TN': 'l10n_tn',
            'CI': 'l10n_ci',
            'CM': 'l10n_cm',
            'DE': 'l10n_de',
            'ES': 'l10n_es',
            'GB': 'l10n_uk',
            'US': 'l10n_us',
            'SA': 'l10n_sa',
            'AE': 'l10n_ae',
        }

        country = getattr(self, 'saas_country_id', None)
        if not country:
            _logger.info("No saas_country_id on instance %s, skipping l10n install", self.name)
            return

        country_code = country.code
        l10n_module = L10N_MAP.get(country_code)
        if not l10n_module:
            _logger.info("No l10n module mapped for country %s on instance %s", country_code, self.name)
            return

        if not self.admin_login or not self.admin_password:
            _logger.warning("No admin credentials to install l10n for %s", self.name)
            return

        server = self.server_id
        base_url = server.server_url.rstrip('/')
        rpc_url = f"{base_url}/jsonrpc"

        try:
            # 1. Authenticate
            auth_resp = requests.post(rpc_url, json={
                'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                'params': {
                    'service': 'common', 'method': 'authenticate',
                    'args': [self.database_name, self.admin_login, self.admin_password, {}],
                },
            }, timeout=30, verify=False)
            uid = auth_resp.json().get('result')
            if not uid:
                _logger.warning("Auth failed for l10n install on %s", self.name)
                return

            # 2. Search module
            search_resp = requests.post(rpc_url, json={
                'jsonrpc': '2.0', 'method': 'call', 'id': 2,
                'params': {
                    'service': 'object', 'method': 'execute_kw',
                    'args': [
                        self.database_name, uid, self.admin_password,
                        'ir.module.module', 'search',
                        [[['name', '=', l10n_module]]],
                    ],
                },
            }, timeout=30, verify=False)
            module_ids = search_resp.json().get('result', [])
            if not module_ids:
                _logger.warning("Module %s not found in instance %s", l10n_module, self.name)
                return

            # 3. Check state (skip if already installed)
            read_resp = requests.post(rpc_url, json={
                'jsonrpc': '2.0', 'method': 'call', 'id': 3,
                'params': {
                    'service': 'object', 'method': 'execute_kw',
                    'args': [
                        self.database_name, uid, self.admin_password,
                        'ir.module.module', 'read',
                        [module_ids, ['state']],
                    ],
                },
            }, timeout=30, verify=False)
            module_info = read_resp.json().get('result', [])
            if module_info and module_info[0].get('state') == 'installed':
                _logger.info("Module %s already installed on %s", l10n_module, self.name)
                return

            # 4. Install (button_immediate_install triggers registry reload on that instance)
            try:
                install_resp = requests.post(rpc_url, json={
                    'jsonrpc': '2.0', 'method': 'call', 'id': 4,
                    'params': {
                        'service': 'object', 'method': 'execute_kw',
                        'args': [
                            self.database_name, uid, self.admin_password,
                            'ir.module.module', 'button_immediate_install',
                            [module_ids],
                        ],
                    },
                }, timeout=120, verify=False)
                result = install_resp.json()
                if result.get('error'):
                    _logger.warning(
                        "L10n install RPC error for %s: %s",
                        self.name, result['error'].get('data', {}).get('message', result['error'])
                    )
                else:
                    _logger.info("L10n module %s install triggered on %s", l10n_module, self.name)
            except requests.exceptions.Timeout:
                # button_immediate_install peut provoquer un restart du worker — normal
                _logger.info(
                    "L10n install timed out for %s (expected if worker restarts): module=%s",
                    self.name, l10n_module
                )

            # 5. Apply chart template via direct registry access (SUPERUSER — contourne les ACL)
            import time as _time
            from odoo import api as _odoo_api, SUPERUSER_ID
            from odoo.modules.registry import Registry as _Registry
            _time.sleep(4)  # Attendre le rechargement du registry post-install
            try:
                _registry = _Registry(self.database_name)
                with _registry.cursor() as _cr:
                    _env = _odoo_api.Environment(_cr, SUPERUSER_ID, {})
                    _company = _env['res.company'].browse(1)
                    _templates = _env['account.chart.template'].search(
                        [('country_id.code', '=', country_code)], limit=1
                    )
                    if not _templates:
                        _logger.warning(
                            "No chart template for country %s on %s", country_code, self.name
                        )
                    else:
                        _templates.try_loading(company=_company, install_demo=False)
                        _logger.info(
                            "Chart template %s applied to main company on %s",
                            country_code, self.name
                        )
            except Exception as _ct_exc:
                _logger.warning(
                    "Failed to apply chart template for country %s on %s: %s",
                    country_code, self.name, _ct_exc
                )

        except requests.exceptions.Timeout:
            _logger.info(
                "L10n install timed out for %s (expected if worker restarts): module=%s",
                self.name, l10n_module
            )
        except Exception as exc:
            _logger.warning("Failed to install l10n module %s on %s: %s", l10n_module, self.name, exc)

    def _create_client_admin(self):
        """
        Créer le compte administrateur client.
        Create client administrator account via RPC.

        Modifie l'utilisateur admin (ID 2) de la base clonée avec les identifiants fournis.
        Utilise les identifiants du template pour s'authentifier à la base clonée.

        Modifies the admin user (ID 2) of the cloned database with provided credentials.
        Uses template admin credentials to authenticate to the cloned database.
        """
        self.ensure_one()

        try:
            # Get template credentials
            template = self.template_id
            template_admin_login = template.template_admin_login
            template_admin_password = template.template_admin_password

            # Generate credentials if not provided
            admin_login = self.admin_login or self.partner_id.email or f"admin@{self.subdomain}"
            admin_password = self.admin_password or self._generate_random_password()
            
            # Get server details
            server = self.server_id
            base_url = server.server_url.rstrip('/')
            rpc_url = f"{base_url}/jsonrpc"

            _logger.info(f"Creating admin account for instance {self.database_name}")
            _logger.info(f"Using template credentials: {template_admin_login}")
            _logger.info(f"New admin login will be: {admin_login}")

            # Use template credentials to update the admin user
            # We'll call execute_kw to update res.users with ID 2
            payload = {
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {
                    'service': 'object',
                    'method': 'execute_kw',
                    'args': [
                        self.database_name,              # database name
                        2,                                # admin user ID
                        template_admin_password,         # current admin password from template
                        'res.users',                     # model
                        'write',                         # method
                        [[2], {                          # write args: [IDs], {values}
                            'name': self.partner_id.name,
                            'login': admin_login,
                            'password': admin_password,
                            'email': self.partner_id.email or admin_login,
                        }]
                    ]
                },
                'id': 1
            }

            _logger.info(f"Updating admin user via RPC: {rpc_url}")

            response = requests.post(
                rpc_url,
                json=payload,
                timeout=30,
                verify=False
            )

            response.raise_for_status()
            result = response.json()

            # Check for RPC errors
            if 'error' in result and result['error']:
                error_data = result['error'].get('data', {})
                error_msg = error_data.get('message', str(result['error']))
                _logger.error(f"Failed to update admin user: {error_msg}")
                # Don't raise error, just log warning and continue
                _logger.warning(f"Admin user configuration may not be complete: {error_msg}")
            else:
                _logger.info(f"Admin user updated successfully for {self.database_name}")

            # Store the credentials
            self.write({
                'admin_login': admin_login,
                'admin_password': admin_password,
            })
            
            _logger.info(f"Admin credentials stored for instance {self.database_name}")

        except requests.exceptions.RequestException as e:
            _logger.error(f"Request error while creating admin: {str(e)}")
            # Generate and store credentials anyway for manual setup if needed
            if not self.admin_login:
                self.admin_login = self.partner_id.email or f"admin@{self.subdomain}"
            if not self.admin_password:
                self.admin_password = self._generate_random_password()
            _logger.warning(f"Admin credentials stored but may need manual configuration")
        except Exception as e:
            _logger.exception(f"Error creating admin account: {str(e)}")
            # Generate and store credentials anyway
            if not self.admin_login:
                self.admin_login = self.partner_id.email or f"admin@{self.subdomain}"
            if not self.admin_password:
                self.admin_password = self._generate_random_password()

    def _configure_subdomain(self):
        """
        Configurer le sous-domaine DNS et reverse proxy.
        Configure subdomain DNS and reverse proxy.
        
        TODO Phase 2: Implement DNS/reverse proxy configuration
        
        Example implementation for Traefik:
            # Add labels to Traefik configuration
            # Or update nginx configuration
            # Or configure Cloudflare DNS via API
            
            import requests
            
            # Example: Cloudflare API
            cloudflare_api_key = config.get('cloudflare_api_key')
            zone_id = config.get('cloudflare_zone_id')
            
            headers = {
                'Authorization': f'Bearer {cloudflare_api_key}',
                'Content-Type': 'application/json',
            }
            
            data = {
                'type': 'A',
                'name': self.subdomain,
                'content': config.get('server_ip'),
                'proxied': True,
            }
            
            response = requests.post(
                f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records',
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                _logger.info(f"DNS record created for {self.domain}")
            else:
                _logger.error(f"DNS creation failed: {response.text}")
        """
        _logger.info(f"TODO Phase 2: Configure DNS for {self.domain}")
        # Placeholder - actual implementation in Phase 2

    def _send_provisioning_email(self):
        """
        Envoyer un email au client avec les détails de connexion à l'instance.
        Send provisioning details email to customer with connection information.

        Utilise le modèle de mail 'mail_template_instance_provisioned' pour
        envoyer un email professionnel avec les détails de l'instance.

        Uses the 'mail_template_instance_provisioned' email template to send
        a professional email with instance connection details.
        """
        self.ensure_one()

        try:
            # Get the email template for instance provisioning
            template = self.env.ref(
                'saas_manager.mail_template_instance_provisioned',
                raise_if_not_found=False
            )

            if not template:
                _logger.warning(
                    f"Email template 'saas_manager.mail_template_instance_provisioned' "
                    f"not found. Skipping email notification for instance {self.name}"
                )
                return False

            # Check if partner has email
            if not self.partner_id.email:
                _logger.warning(
                    f"Customer {self.partner_id.name} has no email address. "
                    f"Cannot send provisioning email for instance {self.name}"
                )
                return False

            _logger.info(
                f"Sending provisioning email to {self.partner_id.email} "
                f"for instance {self.name}"
            )

            # Send the email using the template
            template.send_mail(
                self.id,
                force_send=True,
                raise_exception=False
            )

            _logger.info(
                f"Provisioning email sent successfully to {self.partner_id.email} "
                f"for instance {self.name}"
            )

            return True

        except Exception as e:
            _logger.error(
                f"Failed to send provisioning email for instance {self.name}: {str(e)}",
                exc_info=True
            )
            # Don't raise error - provisioning is complete, email is just notification
            return False

    def _send_suspension_email(self):
        """
        Envoyer un email au client lors de la suspension de l'instance.
        Send suspension notification email to customer.

        Uses the 'mail_template_instance_suspended' email template.
        """
        self.ensure_one()

        try:
            # Get the email template for instance suspension
            template = self.env.ref(
                'saas_manager.mail_template_instance_suspended',
                raise_if_not_found=False
            )

            if not template:
                _logger.warning(
                    f"Email template 'saas_manager.mail_template_instance_suspended' "
                    f"not found. Skipping email notification for instance {self.name}"
                )
                return False

            # Check if partner has email
            if not self.partner_id.email:
                _logger.warning(
                    f"Customer {self.partner_id.name} has no email address. "
                    f"Cannot send suspension email for instance {self.name}"
                )
                return False

            _logger.info(
                f"Sending suspension email to {self.partner_id.email} "
                f"for instance {self.name}"
            )

            # Send the email using the template
            template.send_mail(
                self.id,
                force_send=True,
                raise_exception=False
            )

            _logger.info(
                f"Suspension email sent successfully to {self.partner_id.email} "
                f"for instance {self.name}"
            )

            return True

        except Exception as e:
            _logger.error(
                f"Failed to send suspension email for instance {self.name}: {str(e)}",
                exc_info=True
            )
            # Don't raise error - suspension is complete, email is just notification
            return False

    def _send_reactivation_email(self):
        """
        Envoyer un email au client lors de la réactivation de l'instance.
        Send reactivation notification email to customer.

        Uses the 'mail_template_instance_reactivated' email template.
        """
        self.ensure_one()

        try:
            # Get the email template for instance reactivation
            template = self.env.ref(
                'saas_manager.mail_template_instance_reactivated',
                raise_if_not_found=False
            )

            if not template:
                _logger.warning(
                    f"Email template 'saas_manager.mail_template_instance_reactivated' "
                    f"not found. Skipping email notification for instance {self.name}"
                )
                return False

            # Check if partner has email
            if not self.partner_id.email:
                _logger.warning(
                    f"Customer {self.partner_id.name} has no email address. "
                    f"Cannot send reactivation email for instance {self.name}"
                )
                return False

            _logger.info(
                f"Sending reactivation email to {self.partner_id.email} "
                f"for instance {self.name}"
            )

            # Send the email using the template
            template.send_mail(
                self.id,
                force_send=True,
                raise_exception=False
            )

            _logger.info(
                f"Reactivation email sent successfully to {self.partner_id.email} "
                f"for instance {self.name}"
            )

            return True

        except Exception as e:
            _logger.error(
                f"Failed to send reactivation email for instance {self.name}: {str(e)}",
                exc_info=True
            )
            # Don't raise error - reactivation is complete, email is just notification
            return False

    def _send_termination_email(self):
        """
        Envoyer un email au client lors de la suppression de l'instance.
        Send termination notification email to customer.

        Uses the 'mail_template_instance_terminated' email template.
        """
        self.ensure_one()

        try:
            # Get the email template for instance termination
            template = self.env.ref(
                'saas_manager.mail_template_instance_terminated',
                raise_if_not_found=False
            )

            if not template:
                _logger.warning(
                    f"Email template 'saas_manager.mail_template_instance_terminated' "
                    f"not found. Skipping email notification for instance {self.name}"
                )
                return False

            # Check if partner has email
            if not self.partner_id.email:
                _logger.warning(
                    f"Customer {self.partner_id.name} has no email address. "
                    f"Cannot send termination email for instance {self.name}"
                )
                return False

            _logger.info(
                f"Sending termination email to {self.partner_id.email} "
                f"for instance {self.name}"
            )

            # Send the email using the template
            template.send_mail(
                self.id,
                force_send=True,
                raise_exception=False
            )

            _logger.info(
                f"Termination email sent successfully to {self.partner_id.email} "
                f"for instance {self.name}"
            )

            return True

        except Exception as e:
            _logger.error(
                f"Failed to send termination email for instance {self.name}: {str(e)}",
                exc_info=True
            )
            # Don't raise error - termination is complete, email is just notification
            return False

    def action_suspend(self):
        """
        Suspendre l'instance (non-paiement, expiration).
        Suspend the instance (non-payment, expiration).
        """
        self.ensure_one()
        
        if self.state not in ['active']:
            raise UserError(_('Only active instances can be suspended.'))
        
        self.write({'state': 'suspended'})

        # Inform the agent to block access immediately
        self._send_expiration_to_instance(True, self.expiration_date)

        # Send suspension email to customer
        self._send_suspension_email()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Instance Suspended'),
                'message': _('Instance %s has been suspended') % self.name,
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_reactivate(self):
        """
        Réactiver une instance suspendue.
        Reactivate a suspended instance.
        """
        self.ensure_one()
        
        if self.state not in ['suspended', 'expired']:
            raise UserError(_('Only suspended or expired instances can be reactivated.'))
        
        self.write({'state': 'active'})

        # Lift suspension on the agent side
        self._send_expiration_to_instance(False, self.expiration_date)

        # Send reactivation email to customer
        self._send_reactivation_email()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Instance Reactivated'),
                'message': _('Instance %s is now active') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_terminate(self):
        """
        Terminer définitivement l'instance (supprime la DB).
        Terminate the instance permanently (deletes DB).
        
        Supprime la base de données PostgreSQL via l'API RPC.
        Deletes the PostgreSQL database via RPC API.

        Restricted to SaaS Administrator group only.
        """
        self.ensure_one()
        
        # Check if user is SaaS Administrator
        if not self.env.user.has_group('saas_manager.group_saas_admin'):
            raise UserError(
                _('Only SaaS Administrators can terminate instances.')
            )

        if self.state == 'terminated':
            raise UserError(_('Instance is already terminated.'))
        
        try:
            # Delete the PostgreSQL database via RPC
            self._delete_database()

            # Update instance state
            self.write({
                'state': 'terminated',
                'active': False,
            })

            _logger.info(f"Instance {self.name} ({self.database_name}) terminated successfully")

            # Send termination email to customer
            self._send_termination_email()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Instance Terminated'),
                    'message': _('Instance %s has been terminated and database deleted') % self.name,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Failed to terminate instance {self.name}: {str(e)}")
            raise UserError(
                _('Failed to terminate instance: %s') % str(e)
            )

    def _delete_database(self):
        """
        Supprimer la base de données PostgreSQL via l'API RPC.
        Delete the PostgreSQL database via RPC API.

        Uses the drop_database RPC service.

        Raises:
            UserError: If deletion fails
        """
        self.ensure_one()

        base_url = None

        try:
            # Get server details
            server = self.server_id
            base_url = server.server_url.rstrip('/')
            master_password = server.master_password

            _logger.info(f"Deleting database {self.database_name} on server {server.name}")
            _logger.info(f"Using server URL: {base_url}")

            # Endpoint for database operations
            rpc_url = f"{base_url}/jsonrpc"

            # Payload for dropping the database
            payload = {
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {
                    'service': 'db',
                    'method': 'drop',
                    'args': [
                        master_password,        # master password
                        self.database_name,     # database name to drop
                    ]
                },
                'id': 1
            }

            _logger.info(f"Dropping database via RPC: {self.database_name}")

            # Make RPC call
            response = requests.post(
                rpc_url,
                json=payload,
                timeout=300  # Allow up to 5 minutes for database deletion
            )

            response.raise_for_status()
            result = response.json()

            # Check for RPC errors
            if 'error' in result and result['error']:
                error_data = result['error'].get('data', {})
                error_msg = error_data.get('message', str(result['error']))
                _logger.warning(f"RPC Error: {error_msg}")
                raise UserError(
                    _("Failed to delete database via RPC.\n\nError: %s") % error_msg
                )

            _logger.info(f"Database {self.database_name} deleted successfully")
            return True

        except requests.exceptions.Timeout:
            _logger.error(f"Database deletion timed out for {self.database_name}")
            raise UserError(
                _("Database deletion timed out.\n\n"
                  "Please try again or contact support.")
            )
        except requests.exceptions.RequestException as e:
            _logger.exception(f"Request error during database deletion")
            raise UserError(
                _("Failed to connect to Odoo RPC endpoint.\n\n"
                  "URL: %s\n\n"
                  "Error: %s") % (base_url, str(e))
            )
        except UserError:
            raise
        except Exception as e:
            _logger.exception(f"Unexpected error in _delete_database")
            raise UserError(
                _("An unexpected error occurred while deleting the database.\n\nError: %s") % str(e)
            )

    def action_access_instance(self):
        """
        Ouvrir l'instance dans un nouvel onglet.
        Open instance in a new tab.
        
        Returns:
            dict: Action to open instance URL
        """
        self.ensure_one()
        
        if self.state not in ['active', 'suspended']:
            raise UserError(_('Instance must be active to access it.'))
        
        instance_url = f"{self.protocol}://{self.domain}"

        return {
            'type': 'ir.actions.act_url',
            'url': instance_url,
            'target': 'new',
        }

    @api.model
    def cron_check_subscription_expiry(self):
        """
        CRON: Vérifier les abonnements expirés et suspendre les instances.
        CRON: Check expired subscriptions and suspend instances.
        """
        _logger.info("Running subscription expiry check...")
        
        # Find instances with expired subscriptions
        expired_instances = self.search([
            ('state', '=', 'active'),
            ('expiration_date', '<=', fields.Datetime.now()),
        ])
        
        for instance in expired_instances:
            try:
                instance.action_suspend()  # This will also send suspension email and notify agent
                instance.write({'state': 'suspended'})
                _logger.info(f"Instance {instance.name} marked as suspended due to subscription expiry")
                
            except Exception as e:
                _logger.error(f"Failed to expire instance {instance.name}: {str(e)}")

    @api.model
    def cron_monitor_instances(self):
        """
        CRON: Monitorer les instances (usage, santé).
        CRON: Monitor instances (usage, health).
        
        TODO Phase 2: Implement monitoring
        """
        _logger.info("Running instance monitoring...")
        
        active_instances = self.search([('state', '=', 'active')])
        
        for instance in active_instances:
            try:
                # TODO Phase 2: Check database health, disk usage, etc.
                _logger.debug(f"Monitoring instance {instance.name}")
                
            except Exception as e:
                _logger.error(f"Monitoring failed for {instance.name}: {str(e)}")

    def action_sync_user_limit(self):
        """
        Manually sync user limit to instance.
        Called from button in form view.
        """
        self.ensure_one()
        
        if not self.domain:
            raise UserError(_('Instance has no domain configured.'))
        
        if self.state not in ['active', 'suspended']:
            raise UserError(_('Can only sync active or suspended instances.'))
        
        success = self._send_user_limit_to_instance()
        
        if success:
            self.write({
                'last_sync_date': fields.Datetime.now(),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('User Limit Synced'),
                    'message': _('User limit of %d sent to instance successfully') % self.user_limit,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError(_(
                'Failed to sync user limit with instance. '
                'Check that saas_agent is installed in the instance and that the domain is accessible.'
            ))

    def action_refresh_users_count(self):
        """
        Refresh current users count from instance.
        Called from button in form view.
        """
        self.ensure_one()

        if self.state not in ['active', 'suspended']:
            raise UserError(_('Instance must be active or suspended.'))

        if not self.domain:
            raise UserError(_('Instance has no domain configured.'))

        count = self._get_users_count_from_instance()
        percentage = (count / self.user_limit * 100) if self.user_limit else 0

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Users Count'),
                'message': _('%d users / %d limit (%.1f%%)') % (count, self.user_limit, percentage),
                'type': 'info',
                'sticky': False,
            }
        }

    def _ensure_agent_secret(self):
        self.ensure_one()
        if not self.agent_secret:
            self.agent_secret = self._generate_random_password(32)
        return self.agent_secret

    def _build_instance_url(self):
        protocol = getattr(self, 'protocol', 'https') or 'https'
        if self.domain and (self.domain.startswith('http://') or self.domain.startswith('https://')):
            return self.domain.rstrip('/')
        if self.domain:
            return f"{protocol}://{self.domain}"
        return None

    def _push_agent_secret_to_instance(self):
        """Push agent secret via /saas/bootstrap using server master password.

        No dependency on admin credentials — works even if the client
        changed their admin login/password.
        """
        self.ensure_one()
        base_url = self._build_instance_url()
        if not base_url:
            _logger.warning("No domain to push agent secret for %s", self.name)
            return False

        server = self.server_id
        if not server or not server.master_password:
            _logger.warning(
                "No master password configured on server %s",
                server.name if server else 'N/A',
            )
            return False

        secret = self._ensure_agent_secret()

        try:
            bootstrap_payload = {
                'master_password': server.master_password,
                'agent_secret': secret,
                'instance_uuid': self.database_name,
            }
            response = requests.post(
                f"{base_url}/saas/bootstrap",
                json={'jsonrpc': '2.0', 'params': bootstrap_payload},
                headers={'Content-Type': 'application/json'},
                timeout=30,
                verify=False,
            )
            response.raise_for_status()
            payload = self._parse_agent_response(response)

            if payload.get('success'):
                _logger.info("Agent secret bootstrapped to %s via master password", self.name)
                return True

            _logger.warning(
                "Bootstrap agent secret failed for %s: %s",
                self.name, payload.get('error', 'Unknown error'),
            )
            return False

        except requests.exceptions.RequestException as exc:
            _logger.warning("Failed to bootstrap agent secret to %s: %s", self.name, exc)
            return False
        except Exception as exc:
            _logger.warning("Failed to push agent secret to %s: %s", self.name, exc)
            return False

    def _build_agent_jwt(self, action, extra=None, ttl=300):
        self.ensure_one()
        secret = self._ensure_agent_secret()
        now = int(time.time())
        payload = {
            'action': action,
            'db': self.database_name,
            'instance_uuid': self.database_name,
            'iat': now,
            'exp': now + ttl,
        }
        if extra:
            payload.update(extra)
        return jwt.encode(payload, secret, algorithm='HS256')

    def _call_agent(self, endpoint, token, timeout=15):
        base_url = self._build_instance_url()
        if not base_url:
            raise UserError(_('Instance has no domain configured.'))
        url = f"{base_url}{endpoint}"
        headers = {'Authorization': f'Bearer {token}'}
        return requests.post(url, json={'token': token}, headers=headers, timeout=timeout, verify=False)

    def action_sso_login(self):
        """SSO login via JWT token — no admin credentials needed."""
        self.ensure_one()
        if self.state not in ['active', 'suspended']:
            raise UserError(_('Instance must be active to access it.'))

        if not self._push_agent_secret_to_instance():
            raise UserError(_(
                'Cannot sync agent secret with instance. '
                'Check that saas_agent is installed and the server master password is correct.'
            ))

        user_login = self.agent_impersonate_login or self.admin_login or 'admin'
        token = self._build_agent_jwt('sso', {
            'user_login': user_login,
            'redirect': '/web',
        })

        base_url = self._build_instance_url()
        sso_url = f"{base_url}/saas/sso/jwt?token={token}"

        return {
            'type': 'ir.actions.act_url',
            'url': sso_url,
            'target': 'new',
        }

    def _send_user_limit_to_instance(self):
        self.ensure_one()

        if not self.domain or self.state not in ['active', 'suspended']:
            return False

        try:
            token = self._build_agent_jwt('set_user_limit', {'user_limit': self.user_limit})
            response = self._call_agent('/saas/set_user_limit', token)

            if response.status_code == 200:
                payload = self._parse_agent_response(response)

                if payload.get('success'):
                    _logger.info(
                        f"User limit synced to instance {self.name}:  "
                        f"{self.user_limit} users"
                    )
                    return True
                else:
                    _logger.error(
                        f"Failed to sync user limit to {self.name}: "
                        f"{payload.get('error', 'Unknown error')}"
                    )
                    return False
            else:
                _logger.warning(
                    f"HTTP {response.status_code} when syncing to {self.name}:  "
                    f"{response.text[: 200]}"
                )
                return False

        except requests.exceptions.RequestException as e:
            _logger.error(f"Network error syncing to instance {self.name}: {str(e)}")
            return False
        except Exception as e:
            _logger.error(f"Error syncing user limit to instance {self.name}: {str(e)}")
            return False

    def _get_users_count_from_instance(self):
        self.ensure_one()

        if not self.domain:
            return 0

        try:
            token = self._build_agent_jwt('get_users_count')
            response = self._call_agent('/saas/get_users_count', token)

            if response.status_code == 200:
                payload = self._parse_agent_response(response)

                if payload.get('success'):
                    return payload.get('current_users', 0)
                else:
                    _logger.warning(
                        f"Error getting user count from {self.name}: "
                        f"{payload.get('error', 'Unknown error')}"
                    )
                    return 0
            else:
                _logger.warning(
                    f"HTTP {response.status_code} when fetching users from {self.name}"
                )
                return 0

        except requests.exceptions.RequestException as e:
            _logger.debug(f"Network error fetching users from {self.name}: {str(e)}")
            return 0
        except Exception as e:
            _logger.error(f"Error getting user count from instance {self.name}: {str(e)}")
            return 0

    def cron_sync_all_user_limits(self):
        """
        CRON: Sync user limits to all active instances.
        Run this periodically to keep instances in sync.
        """
        instances = self.search([
            ('state', 'in', ['active', 'suspended']),
            ('domain', '!=', False),
        ])
        
        success_count = 0
        for instance in instances:
            try:
                if instance._send_user_limit_to_instance():
                    success_count += 1
                    instance.write({'last_sync_date': fields.Datetime.now()})
            except Exception as e:
                _logger.error(f"Error syncing instance {instance.name}: {str(e)}")
                continue
        
        _logger.info(
            f"User limit sync completed: {success_count}/{len(instances)} instances synced"
        )

    @api.model
    def cron_check_user_limits(self):
        """
        CRON: Vérifier les limites d'utilisateurs et alerter.
        CRON: Check user limits and alert.
        
        TODO Phase 2: Implement limit checking
        """
        _logger.info("Running user limit check...")
        
        active_instances = self.search([('state', '=', 'active')])
        
        for instance in active_instances:
            try:
                # TODO Phase 2: Query instance database for user count
                # Compare with plan.user_limit
                # Send alert if limit exceeded
                pass
                
            except Exception as e:
                _logger.error(f"Limit check failed for {instance.name}: {str(e)}")

    @api.model_create_multi
    def create(self, vals_list):
        """
        Créer une nouvelle instance SaaS.
        Create a new SaaS instance.

        Assure que partner_id est toujours défini avec l'utilisateur actuel par défaut.
        Ensures that partner_id is always set to the current user's partner by default.

        Args:
            vals_list (list): List of values for the new instances

        Returns:
            SaaSInstance: The created instances
        """
        Stage = self.env['saas.instance.stage']
        for vals in vals_list:
            if not vals.get('partner_id') and self.env.user.partner_id:
                vals['partner_id'] = self.env.user.partner_id.id
            if not vals.get('stage_id'):
                if vals.get('state'):
                    stage = self._stage_for_state(vals['state'])
                    if stage:
                        vals['stage_id'] = stage.id
                else:
                    default_stage_id = self._default_stage_id()
                    if default_stage_id:
                        vals['stage_id'] = default_stage_id
            if vals.get('stage_id') and not vals.get('state'):
                stage = Stage.browse(vals['stage_id'])
                if stage:
                    vals['state'] = stage.state

        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('stage_sync_skip'):
            return super().write(vals)

        if 'stage_id' in vals and 'state' not in vals:
            stage = self.env['saas.instance.stage'].browse(vals['stage_id'])
            if stage:
                vals['state'] = stage.state

        res = super().write(vals)

        if 'state' in vals and 'stage_id' not in vals:
            for record in self:
                stage = record._stage_for_state(record.state)
                if stage and record.stage_id != stage:
                    record.with_context(stage_sync_skip=True).write({'stage_id': stage.id})

        return res

    def _parse_agent_response(self, response):
        data = response.json()
        # Odoo json type routes wrap payload in {'jsonrpc': '2.0', 'result': {...}}
        if isinstance(data, dict) and 'result' in data:
            payload = data.get('result') or {}
        else:
            payload = data
        if not isinstance(payload, dict):
            return {'success': False, 'error': _('Invalid agent response')}
        return payload

    def _send_expiration_to_instance(self, suspended, expiration_date=None):
        self.ensure_one()

        if not self.domain or self.state not in ['active', 'suspended']:
            return False

        payload = {'suspended': suspended}
        if expiration_date:
            payload['expiration_date'] = fields.Datetime.to_string(expiration_date)

        try:
            token = self._build_agent_jwt('set_expiration', payload)
            response = self._call_agent('/saas/set_expiration', token)

            if response.status_code == 200:
                data = self._parse_agent_response(response)
                if data.get('success'):
                    _logger.info(
                        "Expiration status synced to instance %s (suspended=%s)",
                        self.name,
                        suspended,
                    )
                    return True
                _logger.warning(
                    "Agent set_expiration error for %s: %s",
                    self.name,
                    data.get('error', 'Unknown error'),
                )
                return False

            _logger.warning(
                "HTTP %s when sending set_expiration to %s: %s",
                response.status_code,
                self.name,
                response.text[:200],
            )
            return False

        except requests.exceptions.RequestException as exc:
            _logger.error("Network error syncing expiration to %s: %s", self.name, exc)
            return False
        except Exception as exc:
            _logger.error("Error syncing expiration to %s: %s", self.name, exc)
            return False
