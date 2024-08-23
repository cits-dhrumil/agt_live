# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

{
    'name': 'Custom Header Footer',
    'version': '1.2',
    'category': 'Reports',
    'description': """
    Set Custom Header Footer for all Reports
    """,
    'author': 'Caret IT Solutions Pvt. Ltd.',
    'website': 'http://www.caretit.com',
    'depends': ['sale_crm', 'account','cit_reports_extended'],
    'data': [
            'data/paperformate_data.xml',
            'report/ec_layout.xml',
            'report/sale_invoice_reports.xml',
            'view/invoice_reports.xml',
            'view/sale_reports.xml',
        ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
