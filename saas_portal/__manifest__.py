# -*- coding: utf-8 -*-
{
    'name': 'SaaS Portal',
    'version': '18.0.1.0.0',
    'category': 'Administration',
    'summary': 'Portal view for SaaS instances',
    'description': '''
        SaaS Portal - Customer Instance Dashboard
        =========================================
        
        Allow customers to view their SaaS instances in the portal:
        * Instance status (Active, Suspended, Expired)
        * Number of users / User limit
        * Expiration date
        * Quick access to instance
    ''',
    'author': 'GetapERP',
    'website': 'https://www.getap.ma',
    'license': 'LGPL-3',
    'depends': [
        'saas_manager',
        'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'saas_portal/static/src/css/saas_portal.css',
        ],
    },
    'installable': True,
    'auto_install': False,
}

