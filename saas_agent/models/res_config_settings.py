# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import secrets
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    saas_agent_secret = fields.Char(string='Agent Secret', config_parameter='saas_agent.secret')
    saas_agent_impersonate_user_id = fields.Many2one(
        'res.users',
        string='Utilisateur SSO par défaut',
        config_parameter='saas_agent.impersonate_user_id',
    )

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        if not ICP.get_param('saas_agent.secret'):
            ICP.set_param('saas_agent.secret', secrets.token_urlsafe(32))

