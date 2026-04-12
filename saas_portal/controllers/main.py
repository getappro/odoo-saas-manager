# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


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

