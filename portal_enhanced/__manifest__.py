# -*- coding: utf-8 -*-
{
    'name': 'Portal Enhanced',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Modern and beautiful portal design',
    'description': '''
        Portal Enhanced - Beautiful Customer Portal
        ============================================
        
        Enhance the customer portal with:
        * Modern card-based dashboard
        * Smooth animations and transitions
        * Better color scheme and typography
        * Responsive sidebar navigation
        * Welcome banner with user info
        * Quick action buttons
        * Status indicators with icons
    ''',
    'author': 'GetapERP',
    'website': 'https://www.getap.ma',
    'license': 'LGPL-3',
    'depends': [
        'portal',
        'web',
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'portal_enhanced/static/src/scss/portal_enhanced.scss',
            'portal_enhanced/static/src/js/portal_enhanced.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}

