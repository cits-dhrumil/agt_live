# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def _prepare_default_reversal(self, move):
        """ Set reason cancel on credit note """
        res = super()._prepare_default_reversal(move)
        new_origin = ''
        contador = 0
        for moves in self.move_ids:
            contador = contador + 1
            if moves.name:
                if contador > 1:
                    new_origin += moves.name + ', '
                else:
                    new_origin += moves.name

        res.update({
            'reason_cancel': self.reason,
            'invoice_origin': new_origin,
        })
        return res