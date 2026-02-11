# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Partner Extension for SaaS
===========================
Extension du modèle Partner pour les clients SaaS.
Extension of Partner model for SaaS customers.
"""

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class Partner(models.Model):
    """
    Extension of res.partner for SaaS management
    """
    _inherit = 'res.partner'

    saas_instance_ids = fields.One2many(
        'saas.instance',
        'partner_id',
        string='SaaS Instances',
        help="SaaS instances owned by this customer"
    )
    saas_instance_count = fields.Integer(
        string='Instance Count',
        compute='_compute_saas_instance_count',
        help="Number of SaaS instances"
    )
    is_saas_customer = fields.Boolean(
        string='SaaS Customer',
        compute='_compute_is_saas_customer',
        store=True,
        help="This partner is a SaaS customer"
    )

    @api.depends('saas_instance_ids')
    def _compute_saas_instance_count(self):
        """
        Calcule le nombre d'instances SaaS.
        Compute number of SaaS instances.
        """
        for partner in self:
            partner.saas_instance_count = len(partner.saas_instance_ids)

    @api.depends('saas_instance_ids')
    def _compute_is_saas_customer(self):
        """
        Détermine si le partner est un client SaaS.
        Determine if partner is a SaaS customer.
        """
        for partner in self:
            partner.is_saas_customer = bool(partner.saas_instance_ids)

    def action_view_saas_instances(self):
        """
        Voir les instances SaaS du client.
        View customer's SaaS instances.
        
        Returns:
            dict: Action to display instances
        """
        self.ensure_one()
        
        return {
            'name': _('SaaS Instances - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'saas.instance',
            'view_mode': 'list,form,kanban',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
