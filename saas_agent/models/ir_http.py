# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        helper = request.env['saas.expiration.helper']
        if helper.is_access_blocked() and not helper.is_allowed_request():
            return helper.build_block_response()
        return super()._dispatch(endpoint)
