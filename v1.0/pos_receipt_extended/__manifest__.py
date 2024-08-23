# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

{
    'name': 'Pos Receipt Extended',
    'version': '1.1',
    'summary': 'POS Receipt Extended',
    'description': """POS Receipt Extended""",
    'category': 'POS',
    'author': 'Caret IT Solutions Pvt. Ltd.',
    'website': 'http://www.caretit.com',
    'depends': ['point_of_sale'],
    'data': [
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_receipt_extended/static/src/app/screens/receipt_screen/receipt/pos_order_receipt_hash_key.js',
            'pos_receipt_extended/static/src/app/screens/receipt_screen/receipt/pos_receipt.xml',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
