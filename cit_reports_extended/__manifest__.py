# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

{
    'name': "Reports Layouts",
    'summary': """AGT Reports Certification""",
    'description': """
        This module use for invoice, sales payments and picking reports 
    """,
    'author': 'Caret IT Solutions Pvt. Ltd.',
    'website': 'http://www.caretit.com',
    'category': 'Reports',
    'version': '1.2',
    'depends': [
        'base','account','sale',
        'web','stock','agt_certification'
    ],
    'data': [
        'security/security.xml',
        'views/acc_move_view.xml',
        'views/res_company_view.xml',
        'report/report_acc_invoice.xml',
        'report/report_sale_order.xml',
        'report/report_delivery.xml',
        'report/report_acc_payment.xml',
        # 'report/report_external_layouts.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
