# -*- coding: utf-8 -*-
from odoo import fields, models


class SaaSPlan(models.Model):
    _inherit = 'saas.plan'

    subscription_template_id = fields.Many2one(
        'sale.subscription.template',
        string='Subscription Template',
        help='Template utilisée pour créer les abonnements sale.subscription.'
    )

