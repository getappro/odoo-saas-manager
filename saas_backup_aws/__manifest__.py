# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'SaaS Backup AWS',
    'version': '18.0.1.0.0',
    'summary': 'Agent de sauvegarde pour AWS',
    'category': 'Administration',
    'author': 'DeepCode',
    'website': 'https://www.deepcode.ma',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'saas_manager'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/backup_record_views.xml',
        'views/res_config_settings_views.xml',
        'views/saas_instance_views.xml',
    ],
    'external_dependencies': {
        'python': ['boto3'],
    },
    'installable': True,
    'application': False,
}
