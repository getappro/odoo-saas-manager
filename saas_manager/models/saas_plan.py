# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
SaaS Plan Model
===============
Plan d'abonnement avec limites et tarifs.
Subscription plan with limits and pricing.
"""

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SaaSPlan(models.Model):
    """
    SaaS Plan - Subscription Plan
    
    Représente un plan d'abonnement avec ses limites et tarifs.
    Represents a subscription plan with its limits and pricing.
    """
    _name = 'saas.plan'
    _description = 'SaaS Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
        help="Plan name (e.g., 'Starter', 'Professional')"
    )
    code = fields.Char(
        string='Code',
        required=True,
        tracking=True,
        help="Technical code (e.g., 'starter')"
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Display order"
    )
    user_limit = fields.Integer(
        string='User Limit',
        required=True,
        default=5,
        tracking=True,
        help="Maximum number of users"
    )
    storage_limit = fields.Float(
        string='Storage Limit (GB)',
        required=True,
        default=10.0,
        tracking=True,
        help="Maximum storage in GB"
    )
    price_monthly = fields.Float(
        string='Monthly Price',
        tracking=True,
        help="Monthly subscription price"
    )
    price_yearly = fields.Float(
        string='Yearly Price',
        tracking=True,
        help="Yearly subscription price"
    )
    trial_days = fields.Integer(
        string='Trial Days',
        default=14,
        tracking=True,
        help="Free trial period in days"
    )
    features = fields.Html(
        string='Features',
        help="HTML formatted list of features"
    )
    is_popular = fields.Boolean(
        string='Popular Plan',
        default=False,
        help="Mark this plan as popular/recommended"
    )
    description = fields.Text(
        string='Description',
        help="Plan description"
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    instance_count = fields.Integer(
        string='Instance Count',
        compute='_compute_instance_count',
        help="Number of active instances using this plan"
    )
    color = fields.Integer(
        string='Color Index',
        help="Color for kanban view"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help="Currency for pricing"
    )

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Plan code must be unique!'),
        ('user_limit_positive', 'CHECK(user_limit > 0)', 'User limit must be positive!'),
        ('storage_limit_positive', 'CHECK(storage_limit > 0)', 'Storage limit must be positive!'),
        ('price_monthly_positive', 'CHECK(price_monthly >= 0)', 'Monthly price must be positive!'),
        ('price_yearly_positive', 'CHECK(price_yearly >= 0)', 'Yearly price must be positive!'),
    ]

    @api.depends('code')
    def _compute_instance_count(self):
        """
        Calcule le nombre d'instances actives utilisant ce plan.
        Compute the number of active instances using this plan.
        """
        for plan in self:
            plan.instance_count = self.env['saas.instance'].search_count([
                ('plan_id', '=', plan.id),
                ('state', 'in', ['active', 'suspended'])
            ])

    @api.constrains('code')
    def _check_code(self):
        """
        Valider le format du code technique.
        Validate technical code format.
        """
        for plan in self:
            if plan.code and not plan.code.islower():
                raise ValidationError(_('Plan code must be lowercase.'))

    @api.constrains('user_limit', 'storage_limit')
    def _check_limits(self):
        """
        Valider les limites du plan.
        Validate plan limits.
        """
        for plan in self:
            if plan.user_limit < 1:
                raise ValidationError(_('User limit must be at least 1.'))
            if plan.storage_limit < 1.0:
                raise ValidationError(_('Storage limit must be at least 1 GB.'))

    def action_view_instances(self):
        """
        Voir toutes les instances utilisant ce plan.
        View all instances using this plan.
        
        Returns:
            dict: Action to display instances
        """
        self.ensure_one()
        
        return {
            'name': _('Instances with Plan: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'saas.instance',
            'view_mode': 'list,form,kanban',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id},
        }
