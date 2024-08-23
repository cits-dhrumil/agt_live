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
        'account','sale','stock',
        'sale_stock','web','base_vat','delivery','product','point_of_sale'
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
         'views/account_move_view.xml',
         'views/account_view.xml',
         'views/ir_sequence.xml',
         'views/taxonomia.xml',
         'views/product_type.xml',
         'views/product.xml',
         'views/res.xml',
         'views/stock_view.xml',
         'views/exemption_reason.xml',
         'views/orders_history.xml',
         'views/user_finance.xml',
         'views/hist_saft.xml',
         'views/res_config_settings.xml',
         'views/account_resequence_wizard_view.xml',
         'wizard/recall_at.xml',
         'wizard/change_guide.xml',
         'wizard/manual_code.xml',
         'wizard/import_saft_.xml',
         'wizard/export_stock.xml',
         'wizard/call_at_wizard.xml',
         'wizard/wizard_l10n_pt_saft.xml',
         'wizard/cancel_invoice.xml',
         'wizard/alert_atcud.xml',
         'views/ir_sequence_atcud.xml',
         'views/sale_order.xml',
         'views/menus.xml',
         'wizard/cancel_sale_order.xml',
         # 'views/pos_order.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
