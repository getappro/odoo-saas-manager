# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
SaaS Subscription Model
=======================
Gestion des abonnements avec renouvellement automatique.
Subscription management with automatic renewal.
"""

import logging
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SaaSSubscription(models.Model):
    """
    SaaS Subscription - Subscription Management
    
    Gère les abonnements clients avec renouvellement automatique.
    Manages client subscriptions with automatic renewal.
    """
    _name = 'saas.subscription'
    _description = 'SaaS Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        help="Subscription reference"
    )
    instance_id = fields.Many2one(
        'saas.instance',
        string='Instance',
        required=True,
        tracking=True,
        ondelete='cascade',
        help="Related SaaS instance"
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='instance_id.partner_id',
        store=True,
        help="Customer"
    )
    plan_id = fields.Many2one(
        'saas.plan',
        string='Plan',
        required=True,
        tracking=True,
        ondelete='restrict',
        help="Subscription plan"
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help="Subscription start date"
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        help="Subscription end date"
    )
    auto_renew = fields.Boolean(
        string='Auto Renew',
        default=True,
        tracking=True,
        help="Automatically renew subscription"
    )
    is_trial = fields.Boolean(
        string='Trial Period',
        default=False,
        tracking=True,
        help="This is a trial subscription"
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', required=True, tracking=True)
    
    payment_state = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ], string='Payment State', default='pending', tracking=True)
    
    amount = fields.Float(
        string='Amount',
        compute='_compute_amount',
        store=True,
        help="Subscription amount"
    )
    period = fields.Selection([
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], string='Period', required=True, default='monthly', tracking=True)
    
    # TODO Phase 2: Invoice integration (requires 'account' module)
    # invoice_ids = fields.One2many(
    #     'account.move',
    #     'saas_subscription_id',
    #     string='Invoices',
    #     help="Related invoices"
    # )
    invoice_count = fields.Integer(
        string='Invoice Count',
        compute='_compute_invoice_count',
        help="Number of invoices"
    )
    notes = fields.Text(
        string='Notes',
        help="Internal notes"
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help="Currency for subscription"
    )

    _sql_constraints = [
        ('dates_check', 'CHECK(end_date >= start_date)', 'End date must be after start date!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to generate sequence.
        """
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('saas.subscription') or _('New')
        return super(SaaSSubscription, self).create(vals_list)

    @api.depends('plan_id', 'period')
    def _compute_amount(self):
        """
        Calcule le montant de l'abonnement selon le plan et la période.
        Compute subscription amount based on plan and period.
        """
        for subscription in self:
            if subscription.plan_id and subscription.period:
                if subscription.period == 'monthly':
                    subscription.amount = subscription.plan_id.price_monthly
                else:  # yearly
                    subscription.amount = subscription.plan_id.price_yearly
            else:
                subscription.amount = 0.0

    @api.depends('name')  # Placeholder - TODO Phase 2: Link to actual invoices
    def _compute_invoice_count(self):
        """
        Calcule le nombre de factures.
        Compute number of invoices.
        
        TODO Phase 2: Implement with account.move when invoicing is integrated
        """
        for subscription in self:
            # Placeholder - invoice integration in Phase 2
            subscription.invoice_count = 0
            # TODO Phase 2: subscription.invoice_count = len(subscription.invoice_ids)

    @api.onchange('plan_id', 'is_trial')
    def _onchange_plan_trial(self):
        """
        Calculer la date de fin selon le plan et la période d'essai.
        Calculate end date based on plan and trial period.
        """
        if self.plan_id and self.start_date:
            if self.is_trial:
                # Trial period
                trial_days = self.plan_id.trial_days or 14
                self.end_date = self.start_date + relativedelta(days=trial_days)
            else:
                # Regular subscription
                if self.period == 'monthly':
                    self.end_date = self.start_date + relativedelta(months=1)
                else:  # yearly
                    self.end_date = self.start_date + relativedelta(years=1)

    def action_activate(self):
        """
        Activer l'abonnement.
        Activate subscription.
        """
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Only draft subscriptions can be activated.'))
        
        self.write({'state': 'active'})
        
        # Update instance expiration date
        if self.instance_id:
            self.instance_id.write({
                'expiration_date': fields.Datetime.from_string(
                    str(self.end_date) + ' 23:59:59'
                ),
                'subscription_id': self.id,
            })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Subscription Activated'),
                'message': _('Subscription %s is now active') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_renew(self):
        """
        Renouveler l'abonnement.
        Renew subscription.
        """
        self.ensure_one()
        
        if self.state not in ['active', 'expired']:
            raise UserError(_('Only active or expired subscriptions can be renewed.'))
        
        # Create new subscription
        new_start_date = self.end_date + relativedelta(days=1)
        
        if self.period == 'monthly':
            new_end_date = new_start_date + relativedelta(months=1)
        else:  # yearly
            new_end_date = new_start_date + relativedelta(years=1)
        
        new_subscription = self.create({
            'instance_id': self.instance_id.id,
            'plan_id': self.plan_id.id,
            'start_date': new_start_date,
            'end_date': new_end_date,
            'period': self.period,
            'auto_renew': self.auto_renew,
            'is_trial': False,
        })
        
        # Mark current subscription as expired
        self.write({'state': 'expired'})
        
        # Activate new subscription
        new_subscription.action_activate()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Subscription Renewed'),
                'message': _('New subscription %s created') % new_subscription.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_cancel(self):
        """
        Annuler l'abonnement.
        Cancel subscription.
        """
        self.ensure_one()
        
        if self.state == 'cancelled':
            raise UserError(_('Subscription is already cancelled.'))
        
        self.write({
            'state': 'cancelled',
            'auto_renew': False,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Subscription Cancelled'),
                'message': _('Subscription %s has been cancelled') % self.name,
                'type': 'warning',
                'sticky': False,
            }
        }

    @api.model
    def cron_auto_renew(self):
        """
        CRON: Renouvellement automatique des abonnements.
        CRON: Automatic renewal of subscriptions.
        """
        _logger.info("Running subscription auto-renewal...")
        
        # Find subscriptions expiring in the next 7 days with auto_renew
        expiring_soon = fields.Date.today() + relativedelta(days=7)
        
        subscriptions = self.search([
            ('state', '=', 'active'),
            ('auto_renew', '=', True),
            ('end_date', '<=', expiring_soon),
        ])
        
        for subscription in subscriptions:
            try:
                # Check payment state before renewing
                if subscription.payment_state == 'paid':
                    subscription.action_renew()
                    _logger.info(f"Subscription {subscription.name} auto-renewed")
                else:
                    _logger.warning(
                        f"Subscription {subscription.name} not renewed: payment pending"
                    )
                    # TODO Phase 2: Send payment reminder email
                    
            except Exception as e:
                _logger.error(f"Auto-renewal failed for {subscription.name}: {str(e)}")

    def action_view_invoices(self):
        """
        Voir les factures de l'abonnement.
        View subscription invoices.
        
        TODO Phase 2: Implement when account module is integrated
        
        Returns:
            dict: Action to display invoices
        """
        self.ensure_one()
        
        # TODO Phase 2: Implement invoice view
        # return {
        #     'name': _('Invoices for %s') % self.name,
        #     'type': 'ir.actions.act_window',
        #     'res_model': 'account.move',
        #     'view_mode': 'list,form',
        #     'domain': [('saas_subscription_id', '=', self.id)],
        #     'context': {'default_saas_subscription_id': self.id},
        # }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Not Implemented'),
                'message': _('Invoice integration will be added in Phase 2'),
                'type': 'info',
                'sticky': False,
            }
        }
