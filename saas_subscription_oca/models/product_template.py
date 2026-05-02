# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    saas_template_id = fields.Many2one(
        comodel_name="saas.template",
        string="SaaS Template",
        help="Template SaaS à utiliser pour créer les instances.",
    )
    saas_active = fields.Boolean(
        "Available for SaaS Instances", default=True, required=True
    )

