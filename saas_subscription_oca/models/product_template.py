# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    saas_template_id = fields.Many2one(
        comodel_name="saas.template",
        string="SaaS Template",
        help="Template SaaS à utiliser pour créer les instances.",
    )

