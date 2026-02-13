# -*- coding: utf-8 -*-
{
    'name': 'SaaS Subscription OCA',
    'version': '18.0.1.0.0',
    'category': 'Administration',
    'summary': 'Intégration des instances SaaS avec subscription_oca',
    'license': 'LGPL-3',
    'depends': ['saas_manager', 'subscription_oca'],
    'data': [
        'views/saas_instance_views.xml',
        'views/saas_plan_views.xml',
        'views/saas_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

