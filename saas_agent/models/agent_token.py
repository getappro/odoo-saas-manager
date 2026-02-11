# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaaSAgentToken(models.Model):
    _name = 'saas.agent.token'
    _description = 'SaaS Agent SSO Token'
    _order = 'create_date desc'

    token = fields.Char(required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade')
    redirect_url = fields.Char()
    expire_at = fields.Datetime(required=True)
    state = fields.Selection([
        ('new', 'New'),
        ('used', 'Used'),
        ('expired', 'Expired'),
    ], default='new', required=True)
    last_used = fields.Datetime()

    @api.model
    def purge_expired(self):
        expired = self.search([('state', '=', 'new'), ('expire_at', '<', fields.Datetime.now())])
        expired.write({'state': 'expired'})

