# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import api, models


class PosOrder(models.Model):
    _inherit = 'pos.order'


    @api.model
    def get_hash_key(self, order_name):
        order = self.search([('pos_reference', '=', order_name)])
        return order.hash
