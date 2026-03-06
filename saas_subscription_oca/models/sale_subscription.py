# -*- coding: utf-8 -*-
from datetime import datetime, time
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class SaleSubscription(models.Model):
    _inherit = 'sale.subscription'

    saas_instance_id = fields.Many2one(
        'saas.instance',
        string='SaaS Instance',
        ondelete='set null',
        help='Instance SaaS liée.'
    )
    subdomain = fields.Char(
        string='Sous-domaine',
        help='Sous-domaine et nom de base de données pour l\'instance SaaS.'
    )

    @api.constrains('subdomain')
    def _check_subdomain_unique(self):
        for rec in self:
            if rec.subdomain:
                existing = self.env['saas.instance'].search_count([
                    ('subdomain', '=', rec.subdomain),
                ])
                if existing:
                    raise ValidationError(_('Le sous-domaine "%s" est déjà utilisé.') % rec.subdomain)

    def action_create_saas_instance(self):
        self.ensure_one()
        if self.saas_instance_id:
            raise UserError(_('Une instance SaaS est déjà liée à cette souscription.'))

        template, user_limit = self._get_saas_template_and_qty()
        if not template:
            raise UserError(_('Aucun template SaaS défini sur les produits de cette souscription.'))

        if not self.subdomain:
            raise UserError(_('Veuillez définir un sous-domaine avant de créer l\'instance.'))

        instance = self.env['saas.instance'].create({
            'name': f"{self.partner_id.name} - {self.code}",
            'partner_id': self.partner_id.id,
            'template_id': template.id,
            'subdomain': self.subdomain,
            'database_name': self.subdomain.replace('-', '_'),
            'sale_subscription_id': self.id,
            'user_limit': int(user_limit),
            'activation_date': datetime.combine(self.date_start, time.min) if self.date_start else False,
            'expiration_date': datetime.combine(self.recurring_next_date, time.min) if self.recurring_next_date else False,
        })

        self.saas_instance_id = instance.id

        # Provisionner l'instance
        instance.action_provision_instance()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'saas.instance',
            'res_id': instance.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_saas_template_and_qty(self):
        for line in self.sale_subscription_line_ids:
            product = line.product_id
            if product.product_tmpl_id.saas_template_id:
                return product.product_tmpl_id.saas_template_id, line.product_uom_qty
        return False, 0

    def action_view_saas_instance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'saas.instance',
            'res_id': self.saas_instance_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


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
            if 'recurring_next_date' in vals and subscription.recurring_next_date:
                updates['expiration_date'] = datetime.combine(subscription.recurring_next_date, time.min)
            if 'stage_id' in vals and subscription.stage_id:
                target_state = state_map.get(subscription.stage_id.type)
                if target_state and target_state != instance.state:
                    updates['state'] = target_state

            if updates:
                instance.with_context(saas_sync_skip=True).write(updates)

        return res

