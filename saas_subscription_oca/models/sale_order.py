# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from collections import defaultdict

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    saas_subdomain = fields.Char(
        string='Sous-domaine SaaS',
        help="Sous-domaine pour l'instance SaaS. Auto-rempli depuis la référence client.",
    )
    saas_country_id = fields.Many2one(
        'res.country',
        string='Pays localisation SaaS',
        help="Pays dont la localisation comptable sera installée sur l'instance. "
             "Si vide, le pays de l'adresse client est utilisé.",
    )

    @api.onchange('client_order_ref')
    def _onchange_client_order_ref_saas(self):
        if self.client_order_ref and not self.saas_subdomain:
            self.saas_subdomain = self.client_order_ref.strip().lower().replace(' ', '-')

    @api.onchange('partner_id')
    def _onchange_partner_id_saas_country(self):
        if self.partner_id.country_id and not self.saas_country_id:
            self.saas_country_id = self.partner_id.country_id

    def _get_saas_country(self):
        """Retourne le pays SaaS avec fallback sur le pays du client."""
        return self.saas_country_id or self.partner_id.country_id

    def create_subscription(self, lines, subscription_tmpl):
        country = self._get_saas_country()
        subdomain = self.saas_subdomain or (self.client_order_ref or '').strip()
        return super(SaleOrder, self.with_context(
            saas_subdomain=subdomain or False,
            saas_country_id=country.id if country else False,
        )).create_subscription(lines, subscription_tmpl)

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

