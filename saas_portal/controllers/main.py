# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class SaaSWebsiteSaleCheckout(WebsiteSale):
    """Override checkout pour capturer le pays de localisation SaaS."""

    @http.route()
    def extra_info(self, **post):
        result = super().extra_info(**post)
        order = request.website.sale_get_order()
        if not order:
            return result

        # Tenter de lire le pays depuis les POST params
        # Le CMS peut nommer le champ 'saas_country_id', 'country_id', 'pays', etc.
        country = None
        for key in ('saas_country_id', 'country_id', 'pays_id', 'pays'):
            val = post.get(key)
            if val:
                try:
                    country_id = int(val)
                    country = request.env['res.country'].sudo().browse(country_id)
                    if country.exists():
                        break
                except (ValueError, TypeError):
                    # valeur texte : chercher par code ou nom
                    country = request.env['res.country'].sudo().search(
                        ['|', ('code', '=ilike', val), ('name', '=ilike', val)], limit=1
                    )
                    if country:
                        break

        if country:
            order.sudo().saas_country_id = country
            _logger.info("SaaS checkout: country %s captured on order %s", country.code, order.name)
        elif not order.saas_country_id and order.partner_id.country_id:
            # Fallback sur le pays du client
            order.sudo().saas_country_id = order.partner_id.country_id

        return result

    @http.route()
    def checkout(self, **post):
        result = super().checkout(**post)
        order = request.website.sale_get_order()
        if order and not order.saas_country_id and order.partner_id.country_id:
            order.sudo().saas_country_id = order.partner_id.country_id
        return result


class SaaSPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'saas_instance_count' in counters:
            partner = request.env.user.partner_id
            values['saas_instance_count'] = request.env['saas.instance'].sudo().search_count([
                ('partner_id', '=', partner.id),
                ('state', '!=', 'terminated'),
            ])
        return values

    @http.route(['/my/instances', '/my/instances/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_instances(self, page=1, sortby=None, **kw):
        partner = request.env.user.partner_id
        Instance = request.env['saas.instance'].sudo()

        domain = [
            ('partner_id', '=', partner.id),
            ('state', '!=', 'terminated'),
        ]

        searchbar_sortings = {
            'name': {'label': 'Nom', 'order': 'name asc'},
            'date': {'label': 'Date', 'order': 'create_date desc'},
            'state': {'label': 'Statut', 'order': 'state asc'},
        }
        sortby = sortby or 'date'
        order = searchbar_sortings[sortby]['order']

        instance_count = Instance.search_count(domain)
        pager = portal_pager(
            url='/my/instances',
            total=instance_count,
            page=page,
            step=10,
            url_args={'sortby': sortby},
        )
        instances = Instance.search(domain, order=order, limit=10, offset=pager['offset'])

        values = {
            'instances': instances,
            'page_name': 'saas_instances',
            'pager': pager,
            'default_url': '/my/instances',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        }
        return request.render('saas_portal.portal_my_instances', values)

    @http.route(['/my/instances/<int:instance_id>'], type='http', auth='user', website=True)
    def portal_instance_detail(self, instance_id, **kw):
        partner = request.env.user.partner_id
        instance = request.env['saas.instance'].sudo().search([
            ('id', '=', instance_id),
            ('partner_id', '=', partner.id),
        ], limit=1)

        if not instance:
            return request.redirect('/my/instances')

        values = {
            'instance': instance,
            'page_name': 'saas_instance_detail',
        }
        return request.render('saas_portal.portal_instance_detail', values)


