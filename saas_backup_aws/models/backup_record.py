# -*- coding: utf-8 -*-
import base64
import datetime
import logging
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaaSBackupRecord(models.Model):
    _name = 'saas.backup.record'
    _description = 'SaaS Backup Record'
    _order = 'create_date desc'

    name = fields.Char(string='Name', required=True, default=lambda self: _('SaaS Backup'))
    instance_id = fields.Many2one('saas.instance', string='Instance', required=True, ondelete='cascade')
    backup_type = fields.Selection([
        ('manual', 'Manual'),
        ('auto', 'Automatic'),
    ], string='Type', default='manual', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], string='Status', default='pending', tracking=True)
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user)
    s3_bucket = fields.Char(string='S3 Bucket', readonly=True)
    s3_key = fields.Char(string='S3 Key', readonly=True)
    s3_region = fields.Char(string='S3 Region', readonly=True)
    size_bytes = fields.Integer(string='Size (bytes)', readonly=True)
    url = fields.Char(string='S3 URL', readonly=True)
    message = fields.Text(string='Message')
    started_at = fields.Datetime(string='Started At')
    done_at = fields.Datetime(string='Completed At')
    duration_seconds = fields.Float(string='Duration (s)', compute='_compute_duration', store=False)

    @api.depends('started_at', 'done_at')
    def _compute_duration(self):
        for rec in self:
            if rec.started_at and rec.done_at:
                rec.duration_seconds = (rec.done_at - rec.started_at).total_seconds()
            else:
                rec.duration_seconds = 0.0

    def run_backup(self):
        for rec in self:
            rec._run_single_backup()

    def _run_single_backup(self):
        self.ensure_one()
        if self.state == 'running':
            return
        self.write({'state': 'running', 'started_at': fields.Datetime.now(), 'message': False})
        start = datetime.datetime.utcnow()
        try:
            service = self.env['saas.backup.service']
            upload = service.perform_backup(self)
            self.write({
                'state': 'done',
                'done_at': fields.Datetime.now(),
                's3_bucket': upload.get('bucket'),
                's3_key': upload.get('key'),
                's3_region': upload.get('region'),
                'size_bytes': upload.get('size'),
                'url': upload.get('url'),
                'message': _('Backup completed successfully'),
            })
        except Exception as exc:
            _logger.exception('Backup failed for instance %s', self.instance_id.name)
            self.write({
                'state': 'failed',
                'done_at': fields.Datetime.now(),
                'message': str(exc),
            })
            raise
        finally:
            end = datetime.datetime.utcnow()
            if not self.duration_seconds:
                self.duration_seconds = (end - start).total_seconds()


class SaaSBackupService(models.AbstractModel):
    _name = 'saas.backup.service'
    _description = 'SaaS Backup Service'

    def _get_conf(self):
        ICP = self.env['ir.config_parameter'].sudo()
        access = ICP.get_param('saas_backup_aws.s3_access_key_id')
        secret = ICP.get_param('saas_backup_aws.s3_secret_access_key')
        region = ICP.get_param('saas_backup_aws.s3_region_name')
        bucket = ICP.get_param('saas_backup_aws.s3_bucket_name')
        prefix = ICP.get_param('saas_backup_aws.s3_prefix') or 'saas_backups'
        retention = int(ICP.get_param('saas_backup_aws.backup_retention') or 5)
        auto_enabled = ICP.get_param('saas_backup_aws.auto_backup_enabled') in ('1', 'true', 'True')
        interval = int(ICP.get_param('saas_backup_aws.auto_backup_interval_hours') or 24)
        if not all([access, secret, region, bucket]):
            raise UserError(_('S3 configuration is incomplete.'))
        return {
            'access': access,
            'secret': secret,
            'region': region,
            'bucket': bucket,
            'prefix': prefix.strip('/'),
            'retention': max(retention, 0),
            'auto_enabled': auto_enabled,
            'interval_hours': max(interval, 1),
        }

    def _s3_client(self, conf):
        import boto3
        return boto3.client(
            's3',
            region_name=conf['region'],
            aws_access_key_id=conf['access'],
            aws_secret_access_key=conf['secret'],
        )

    def _call_backup_rpc(self, instance):
        base_url = instance.server_id.server_url.rstrip('/')
        rpc_url = f"{base_url}/jsonrpc"
        payload = {
            'jsonrpc': '2.0',
            'method': 'call',
            'params': {
                'service': 'db',
                'method': 'backup',
                'args': [instance.server_id.master_password, instance.database_name, 'zip'],
            },
            'id': 1,
        }
        resp = requests.post(rpc_url, json=payload, timeout=600, verify=False)
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data and data['error']:
            raise UserError(data['error'].get('message') or _('Backup RPC error'))
        result = data.get('result')
        if not result:
            raise UserError(_('Empty backup payload'))
        try:
            return base64.b64decode(result)
        except Exception as exc:
            raise UserError(_('Invalid backup content: %s') % exc)

    def perform_backup(self, record):
        conf = self._get_conf()
        content = self._call_backup_rpc(record.instance_id)
        size = len(content)
        now = fields.Datetime.now()
        key = f"{conf['prefix']}/{record.instance_id.database_name}/{now.strftime('%Y/%m/%d')}/{record.instance_id.database_name}-{now.strftime('%Y%m%d-%H%M%S')}.zip"
        client = self._s3_client(conf)
        client.put_object(
            Bucket=conf['bucket'],
            Key=key,
            Body=content,
            ServerSideEncryption='AES256',
        )
        self._apply_retention(record.instance_id, conf, keep_key=key)
        return {
            'bucket': conf['bucket'],
            'key': key,
            'region': conf['region'],
            'size': size,
            'url': f"s3://{conf['bucket']}/{key}",
        }

    def _apply_retention(self, instance, conf, keep_key=None):
        if conf['retention'] <= 0:
            return
        domain = [('instance_id', '=', instance.id), ('state', '=', 'done')]
        backups = self.env['saas.backup.record'].sudo().search(domain, order='create_date desc', offset=conf['retention'])
        if not backups:
            return
        client = self._s3_client(conf)
        for backup in backups:
            if backup.s3_bucket and backup.s3_key:
                try:
                    client.delete_object(Bucket=backup.s3_bucket, Key=backup.s3_key)
                except Exception:
                    _logger.warning('Failed to delete old backup %s', backup.s3_key)
            backup.unlink()

    @api.model
    def cron_auto_backup(self):
        try:
            conf = self._get_conf()
        except UserError:
            _logger.warning('Auto backup skipped: missing config')
            return
        if not conf['auto_enabled']:
            return
        instances = self.env['saas.instance'].sudo().search([('state', 'in', ['active', 'suspended'])])
        for instance in instances:
            last = self.env['saas.backup.record'].sudo().search([
                ('instance_id', '=', instance.id),
                ('backup_type', '=', 'auto'),
                ('state', '=', 'done'),
            ], order='done_at desc', limit=1)
            if last and last.done_at and (fields.Datetime.now() - last.done_at).total_seconds() < conf['interval_hours'] * 3600:
                continue
            rec = self.env['saas.backup.record'].sudo().create({
                'name': f"Auto backup {instance.database_name}",
                'instance_id': instance.id,
                'backup_type': 'auto',
                'state': 'pending',
            })
            try:
                rec.run_backup()
            except Exception as exc:
                _logger.warning('Auto backup failed for %s: %s', instance.name, exc)
                continue

