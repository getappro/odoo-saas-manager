# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from collections import defaultdict

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def group_subscription_lines(self):
        """
        Group Sale Order Lines by their product variant's subscription template
        instead of product template's subscription template.
        """
        grouped = defaultdict(list)
        for order_line in self.order_line.filtered(
            lambda line: line.product_id.subscribable
        ):
            template = (
                order_line.product_id.subscription_template_id
                or order_line.product_id.product_tmpl_id.subscription_template_id
            )
            grouped[template].append(order_line)
        return grouped

