# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Tests for SaaS Server Model
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestSaaSServer(TransactionCase):
    """Test cases for saas.server model"""

    def setUp(self):
        """Set up test data"""
        super().setUp()

        self.server = self.env['saas.server'].create({
            'name': 'Test Server',
            'code': 'test-server-1',
            'server_url': 'http://localhost:8069',
            'server_ip': '127.0.0.1',
            'server_port': 8069,
            'db_host': 'localhost',
            'db_port': 5432,
            'db_user': 'odoo',
            'db_password': 'odoo',
            'master_password': 'admin',
            'cpu_cores': 4,
            'memory_gb': 16,
            'disk_gb': 500,
            'max_instances': 100,
            'state': 'draft',
        })

    def test_server_creation(self):
        """Test server creation"""
        self.assertIsNotNone(self.server)
        self.assertEqual(self.server.name, 'Test Server')
        self.assertEqual(self.server.code, 'test-server-1')
        self.assertEqual(self.server.state, 'draft')

    def test_code_unique(self):
        """Test that server code must be unique"""
        with self.assertRaises(Exception):
            # Try to create a server with the same code
            self.env['saas.server'].create({
                'name': 'Another Server',
                'code': 'test-server-1',  # Same code
                'server_url': 'http://another:8069',
            })

    def test_code_lowercase(self):
        """Test that server code must be lowercase"""
        with self.assertRaises(ValidationError):
            self.env['saas.server'].create({
                'name': 'Invalid Server',
                'code': 'InvalidCode',  # Not lowercase
                'server_url': 'http://localhost:8069',
            })

    def test_server_url_validation(self):
        """Test that server URL must start with http:// or https://"""
        with self.assertRaises(ValidationError):
            self.env['saas.server'].create({
                'name': 'Invalid URL Server',
                'code': 'invalid-url',
                'server_url': 'ftp://localhost:8069',  # Invalid protocol
            })

    def test_max_instances_validation(self):
        """Test that max_instances must be > 0"""
        with self.assertRaises(ValidationError):
            self.env['saas.server'].create({
                'name': 'Invalid Capacity Server',
                'code': 'invalid-capacity',
                'server_url': 'http://localhost:8069',
                'max_instances': 0,
            })

    def test_instance_count_compute(self):
        """Test that instance count is computed correctly"""
        # Create instances
        template = self.env['saas.template'].create({
            'name': 'Test Template',
            'code': 'test-template',
            'template_db': 'test_template_db',
        })

        plan = self.env['saas.plan'].create({
            'name': 'Test Plan',
            'code': 'test-plan',
        })

        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
        })

        # Create instances on this server
        instance1 = self.env['saas.instance'].create({
            'name': 'Test Instance 1',
            'database_name': 'test_instance_1',
            'subdomain': 'test1',
            'template_id': template.id,
            'plan_id': plan.id,
            'server_id': self.server.id,
            'partner_id': partner.id,
        })

        instance2 = self.env['saas.instance'].create({
            'name': 'Test Instance 2',
            'database_name': 'test_instance_2',
            'subdomain': 'test2',
            'template_id': template.id,
            'plan_id': plan.id,
            'server_id': self.server.id,
            'partner_id': partner.id,
        })

        # Refresh server
        self.server.refresh()

        # Check instance count
        self.assertEqual(self.server.instance_count, 2)

    def test_available_capacity_compute(self):
        """Test that available capacity is computed correctly"""
        self.assertEqual(self.server.available_capacity, 100.0)  # 0/100 instances

        # The capacity depends on instance_count and max_instances
        # available_capacity = ((max_instances - instance_count) / max_instances) * 100

    def test_is_online_compute(self):
        """Test that is_online is computed based on state"""
        # Initially draft, so not online
        self.assertFalse(self.server.is_online)

        # Activate server
        self.server.state = 'active'
        self.assertTrue(self.server.is_online)

        # Deactivate
        self.server.state = 'offline'
        self.assertFalse(self.server.is_online)

    def test_delete_server_with_instances_fails(self):
        """Test that cannot delete server with instances"""
        # Create an instance
        template = self.env['saas.template'].create({
            'name': 'Test Template',
            'code': 'test-template-2',
            'template_db': 'test_template_db_2',
        })

        plan = self.env['saas.plan'].create({
            'name': 'Test Plan',
            'code': 'test-plan-2',
        })

        partner = self.env['res.partner'].create({
            'name': 'Test Partner 2',
        })

        instance = self.env['saas.instance'].create({
            'name': 'Test Instance',
            'database_name': 'test_instance',
            'subdomain': 'test',
            'template_id': template.id,
            'plan_id': plan.id,
            'server_id': self.server.id,
            'partner_id': partner.id,
        })

        # Try to delete server - should fail
        with self.assertRaises(UserError):
            self.server.unlink()

    def test_deactivate_server_with_instances_fails(self):
        """Test that cannot deactivate server with instances"""
        # Create an instance
        template = self.env['saas.template'].create({
            'name': 'Test Template',
            'code': 'test-template-3',
            'template_db': 'test_template_db_3',
        })

        plan = self.env['saas.plan'].create({
            'name': 'Test Plan',
            'code': 'test-plan-3',
        })

        partner = self.env['res.partner'].create({
            'name': 'Test Partner 3',
        })

        instance = self.env['saas.instance'].create({
            'name': 'Test Instance',
            'database_name': 'test_instance',
            'subdomain': 'test',
            'template_id': template.id,
            'plan_id': plan.id,
            'server_id': self.server.id,
            'partner_id': partner.id,
        })

        # Try to deactivate - should fail
        with self.assertRaises(UserError):
            self.server.action_deactivate()

    def test_get_available_server(self):
        """Test get_available_server method"""
        # Make server active and available
        self.server.state = 'active'
        self.server.max_instances = 100

        # Get available server
        available = self.env['saas.server'].get_available_server(min_capacity_percent=20)

        # Should return our server
        self.assertEqual(available.id, self.server.id)

    def test_get_available_server_no_capacity(self):
        """Test get_available_server fails when no capacity"""
        # Make server full
        self.server.state = 'active'
        self.server.max_instances = 1

        # Create an instance to fill it
        template = self.env['saas.template'].create({
            'name': 'Test Template',
            'code': 'test-template-full',
            'template_db': 'test_template_db_full',
        })

        plan = self.env['saas.plan'].create({
            'name': 'Test Plan Full',
            'code': 'test-plan-full',
        })

        partner = self.env['res.partner'].create({
            'name': 'Test Partner Full',
        })

        instance = self.env['saas.instance'].create({
            'name': 'Test Instance Full',
            'database_name': 'test_instance_full',
            'subdomain': 'testfull',
            'template_id': template.id,
            'plan_id': plan.id,
            'server_id': self.server.id,
            'partner_id': partner.id,
        })

        # Try to get available server - should fail
        with self.assertRaises(UserError):
            self.env['saas.server'].get_available_server(min_capacity_percent=20)

