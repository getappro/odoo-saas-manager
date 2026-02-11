# -*- coding: utf-8 -*-
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from odoo import models, fields, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    s3_access_key_id = fields.Char(
        string='S3 Access Key',
        config_parameter='saas_backup_aws.s3_access_key_id',
        groups='base.group_system',
        help='AWS IAM access key used for backups'
    )
    s3_secret_access_key = fields.Char(
        string='S3 Secret Key',
        config_parameter='saas_backup_aws.s3_secret_access_key',
        groups='base.group_system',
        password=True,
        help='AWS IAM secret key used for backups'
    )
    s3_region_name = fields.Char(
        string='S3 Region',
        config_parameter='saas_backup_aws.s3_region_name',
        groups='base.group_system',
        default='eu-west-1'
    )
    s3_bucket_name = fields.Char(
        string='S3 Bucket',
        config_parameter='saas_backup_aws.s3_bucket_name',
        groups='base.group_system'
    )
    s3_prefix = fields.Char(
        string='S3 Prefix',
        config_parameter='saas_backup_aws.s3_prefix',
        groups='base.group_system',
        default='saas_backups'
    )
    backup_retention = fields.Integer(
        string='Retention (backups)',
        config_parameter='saas_backup_aws.backup_retention',
        groups='base.group_system',
        default=5
    )
    auto_backup_enabled = fields.Boolean(
        string='Automatic Backups',
        config_parameter='saas_backup_aws.auto_backup_enabled',
        groups='base.group_system',
        default=False
    )
    auto_backup_interval_hours = fields.Integer(
        string='Auto Interval (hours)',
        config_parameter='saas_backup_aws.auto_backup_interval_hours',
        groups='base.group_system',
        default=24
    )

    def action_test_s3_connection(self):
        self.ensure_one()
        conf = self._get_backup_conf()
        try:
            client = boto3.client(
                's3',
                region_name=conf['region'],
                aws_access_key_id=conf['access_key'],
                aws_secret_access_key=conf['secret_key'],
            )
            client.head_bucket(Bucket=conf['bucket'])
        except (ClientError, BotoCoreError) as exc:
            raise UserError(_('S3 connection failed: %s') % exc)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('S3 connection OK'),
                'message': _('Bucket %s reachable in %s') % (conf['bucket'], conf['region']),
                'type': 'success',
                'sticky': False,
            }
        }

    def _get_backup_conf(self):
        self.ensure_one()
        access = self.s3_access_key_id or self.env['ir.config_parameter'].sudo().get_param('saas_backup_aws.s3_access_key_id')
        secret = self.s3_secret_access_key or self.env['ir.config_parameter'].sudo().get_param('saas_backup_aws.s3_secret_access_key')
        region = self.s3_region_name or self.env['ir.config_parameter'].sudo().get_param('saas_backup_aws.s3_region_name')
        bucket = self.s3_bucket_name or self.env['ir.config_parameter'].sudo().get_param('saas_backup_aws.s3_bucket_name')
        prefix = self.s3_prefix or self.env['ir.config_parameter'].sudo().get_param('saas_backup_aws.s3_prefix') or 'saas_backups'
        if not all([access, secret, region, bucket]):
            raise UserError(_('S3 configuration is incomplete.'))
        return {
            'access_key': access,
            'secret_key': secret,
            'region': region,
            'bucket': bucket,
            'prefix': prefix,
        }

