# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaaSInstance(models.Model):
    _inherit = 'saas.instance'

    sale_subscription_id = fields.Many2one(
        'sale.subscription',
        string='Subscription',
        ondelete='set null',
        copy=False,
        help='Abonnement subscription_oca lié à cette instance.'
    )

    def _get_subscription_stage(self, stage_type):
        try:
            return self.env['sale.subscription.stage'].search([('type', '=', stage_type)], limit=1)
        except Exception:
            return False

    def _create_sale_subscription(self):
        self.ensure_one()
        if not self.plan_id.subscription_template_id:
            raise UserError(_("Plan %s n'a pas de template d'abonnement définie.") % self.plan_id.display_name)

        pricelist = self.partner_id.property_product_pricelist or self.env['product.pricelist'].search([], limit=1)
        if not pricelist:
            raise UserError(_('Aucune liste de prix disponible pour créer un abonnement.'))

        vals = {
            'partner_id': self.partner_id.id,
            'template_id': self.plan_id.subscription_template_id.id,
            'pricelist_id': pricelist.id,
            'saas_instance_id': self.id,
            'date_start': fields.Date.context_today(self),
        }
        if self.expiration_date:
            vals['date'] = fields.Date.to_date(self.expiration_date)

        subscription = self.env['sale.subscription'].create(vals)
        if subscription.stage_id.type != 'in_progress':
            subscription.with_context(saas_sync_skip=True).action_start_subscription()

        self.sale_subscription_id = subscription
        return subscription

    def _sync_subscription_from_instance(self, subscription, previous_state, vals):
        if not subscription.exists():
            return

        update_vals = {}
        if 'activation_date' in vals and self.activation_date:
            update_vals['date_start'] = fields.Date.to_date(self.activation_date)
        if 'expiration_date' in vals and self.expiration_date:
            update_vals['date'] = fields.Date.to_date(self.expiration_date)

        state_map = {
            'draft': 'draft',
            'provisioning': 'pre',
            'active': 'in_progress',
            'suspended': 'in_progress',
            'expired': 'post',
            'terminated': 'post',
        }

        if self.state != previous_state:
            stage_type = state_map.get(self.state)
            if self.state in ['terminated', 'expired']:
                try:
                    subscription.with_context(saas_sync_skip=True).close_subscription()
                except Exception:
                    # Si l'abonnement ne peut pas être fermé, on l'ignore
                    pass
            elif stage_type:
                try:
                    stage = self._get_subscription_stage(stage_type)
                    if stage and stage.exists() and subscription.stage_id != stage:
                        subscription.with_context(saas_sync_skip=True).write({'stage_id': stage.id})
                except Exception:
                    # Si la synchronisation échoue, on l'ignore pour éviter les erreurs
                    pass
            if self.state == 'suspended':
                update_vals['to_renew'] = True

        if update_vals:
            try:
                subscription.with_context(saas_sync_skip=True).write(update_vals)
            except Exception:
                # Si l'écriture échoue, on l'ignore
                pass

    def write(self, vals):
        previous_state = {rec.id: rec.state for rec in self}
        res = super().write(vals)

        for record in self:
            subscription = record.sale_subscription_id
            if not subscription and record.state == 'active':
                try:
                    subscription = record._create_sale_subscription()
                except Exception:
                    # Si la création d'abonnement échoue, on continue
                    continue

            if subscription and subscription.exists():
                try:
                    record._sync_subscription_from_instance(subscription, previous_state.get(record.id), vals)
                except Exception:
                    # Si la synchronisation échoue, on l'ignore pour éviter de bloquer la terminaison
                    pass
        return res

