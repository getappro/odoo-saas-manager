# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _check_user_limit_after_change(self, helper, before_count, limit):
        after_count = helper.count_billable_users()
        if after_count > limit and after_count > before_count:
            if limit:
                message = _(
                    'User limit of %d reached. Deactivate a user before adding another.'
                ) % limit
            else:
                message = _(
                    'User creation blocked: user limit is 0. Increase the limit to add users.'
                )
            raise UserError(message)

    @api.model_create_multi
    def create(self, vals_list):
        helper = self.env['saas.user.limit.helper']
        limit = helper._get_user_limit()
        before_count = helper.count_billable_users()
        records = super().create(vals_list)
        self._check_user_limit_after_change(helper, before_count, limit)
        return records

    def write(self, vals):
        affects_limit = any(key in vals for key in ('active', 'share', 'groups_id', 'login'))
        if not affects_limit:
            return super().write(vals)

        helper = self.env['saas.user.limit.helper']
        limit = helper._get_user_limit()
        before_count = helper.count_billable_users()
        res = super().write(vals)
        self._check_user_limit_after_change(helper, before_count, limit)
        return res

