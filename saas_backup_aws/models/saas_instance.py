# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaaSInstance(models.Model):
    _inherit = 'saas.instance'

    backup_count = fields.Integer(string='Backups', compute='_compute_backup_count')

    def _compute_backup_count(self):
        Backup = self.env['saas.backup.record'].sudo()
        for rec in self:
            rec.backup_count = Backup.search_count([('instance_id', '=', rec.id)])

    def action_backup_now(self):
        self.ensure_one()
        if self.state not in ['active', 'suspended']:
            raise UserError(_('Instance must be active or suspended to backup.'))
        backup = self.env['saas.backup.record'].sudo().create({
            'name': _('Backup %s') % self.database_name,
            'instance_id': self.id,
            'backup_type': 'manual',
        })
        backup.run_backup()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Backup launched'),
                'message': _('Backup stored to S3 for %s') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_open_backups(self):
        self.ensure_one()
        action = self.env.ref('saas_backup_aws.action_saas_backup_record').read()[0]
        action['domain'] = [('instance_id', '=', self.id)]
        action['context'] = {'default_instance_id': self.id}
        return action

