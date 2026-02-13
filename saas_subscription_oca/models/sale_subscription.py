# -*- coding: utf-8 -*-
from datetime import datetime, time
from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SaleSubscription(models.Model):
    _inherit = 'sale.subscription'

    saas_instance_id = fields.Many2one(
        'saas.instance',
        string='SaaS Instance',
        ondelete='set null',
        help='Instance SaaS liée.'
    )

    def write(self, vals):
        if vals.get('stage_id'):
            target_stage = self.env['sale.subscription.stage'].browse(vals['stage_id'])
            if target_stage.type == 'in_progress':
                terminated = self.filtered(lambda sub: sub.saas_instance_id and sub.saas_instance_id.state == 'terminated')
                if terminated:
                    raise ValidationError(_('Impossible de réactiver un abonnement lié à une instance terminée.'))

        res = super().write(vals)
        if self.env.context.get('saas_sync_skip'):
            return res

        state_map = {
            'in_progress': 'active',
            'pre': 'provisioning',
            'draft': 'draft',
            'post': 'expired',
        }
        for subscription in self:
            instance = subscription.saas_instance_id
            if not instance or instance.state == 'terminated':
                continue

            updates = {}
            if 'date_start' in vals and subscription.date_start:
                updates['activation_date'] = datetime.combine(subscription.date_start, time.min)
            if 'date' in vals and subscription.date:
                updates['expiration_date'] = datetime.combine(subscription.date, time.min)
            if 'stage_id' in vals and subscription.stage_id:
                target_state = state_map.get(subscription.stage_id.type)
                if target_state and target_state != instance.state:
                    updates['state'] = target_state

            if updates:
                instance.with_context(saas_sync_skip=True).write(updates)

        return res

