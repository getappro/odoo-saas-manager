# -*- coding: utf-8 -*-
from odoo import models


class SaaSUserLimitHelper(models.AbstractModel):
    _name = 'saas.user.limit.helper'
    _description = 'SaaS User Limit Helper'

    def _get_user_limit(self):
        icp = self.env['ir.config_parameter'].sudo()
        raw = icp.get_param('saas_agent.user_limit')
        try:
            limit = int(raw) if raw is not None else 0
        except (TypeError, ValueError):
            return 0
        return max(limit, 0)

    def _billable_domain(self):
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)

        domain = [
            ('active', '=', True),
            ('login', '!=', False),
            ('share', '=', False),
        ]
        if portal_group:
            domain.append(('groups_id', 'not in', portal_group.ids))
        return domain

    def count_billable_users(self):
        return self.env['res.users'].sudo().search_count(self._billable_domain())

    def is_billable_user(self, user):
        user = user.sudo()
        if not user.active or not user.login or user.share:
            return False
        if user.has_group('base.group_portal'):
            return False
        return True

