# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

{
    'name': "AGT Certification",
    'summary': """AGT Certifications""",
    'description': """
       This module generate hash code functionality with invoice
        , sale, pickings nad pos
    """,
    'author': 'Caret IT Solutions Pvt. Ltd.',
    'website': 'http://www.caretit.com',
    'category': 'Accounting',
    'version': '1.2',
    'depends': [
        'base',
        'account', 'sale', 'stock',
        'sale_stock', 'web', 'base_vat', 'delivery', 'product', 'point_of_sale'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/acc_security.xml',
        'data/tipos_produtos_saft.xml',
        'data/data_GT.xml',
        'data/res_lang.xml',
        'data/taxonomias_data.xml',
        'data/ir_sequence_type.xml',
        'data/sequence.xml',
        'data/journal_data.xml',
        'views/account_journal_view.xml',
        'views/res.xml',
        'views/account_view.xml',
        'views/sequence.xml',
        'views/taxonomia.xml',
        'views/user_finance.xml',
        'views/account_move_view.xml',
        'views/stock_view.xml',
        'views/exemption_reason.xml',
        'views/orders_history.xml',
        'views/hist_saft.xml',
        'views/product_type.xml',
        'views/product.xml',
        'views/res_config_settings.xml',
        'views/account_resequence_wizard_view.xml',
        'views/sequence_atcud.xml',
        'views/sale_order.xml',
        'views/menus.xml',
        'wizard/manual_code.xml',
        'wizard/import_saft_.xml',
        'wizard/export_saft_file.xml',
        'wizard/alert_atcud.xml',
        'wizard/change_guide.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
