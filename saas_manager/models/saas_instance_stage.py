# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class SaaSInstanceStage(models.Model):
    _name = 'saas.instance.stage'
    _description = 'SaaS Instance Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('provisioning', 'Provisioning'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ], required=True, default='draft', string='Status')
    fold = fields.Boolean(string='Folded in Kanban')
    color = fields.Integer(string='Color Index')
    active = fields.Boolean(default=True)

    @api.model
    def name_create(self, name):
        # Quick-create: set state draft and return id/name tuple
        stage = self.create({'name': name, 'state': 'draft'})
        return stage.id, stage.display_name
