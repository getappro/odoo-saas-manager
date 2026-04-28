# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaaSInstance(models.Model):
    _inherit = 'saas.instance'

    sale_subscription_id = fields.Many2one(
        'sale.subscription',
        string='Subscription',
        ondelete='set null',
        copy=False,
        help='Abonnement subscription_oca lié à cette instance.'
    )
    saas_country_id = fields.Many2one(
        'res.country',
        string='Pays localisation',
        help="Pays dont le module l10n est installé sur cette instance.",
    )
