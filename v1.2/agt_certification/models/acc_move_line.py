# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from datetime import datetime
from odoo import models, api, _
from odoo.exceptions import ValidationError, UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def date_format(data, tipo='DateType'):
        d = datetime.strptime(data[:19], '%Y-%m-%d %H:%M:%S')
        if tipo == 'DateType':
            return d.strftime('%Y-%m-%d')
        else:
            return d.strftime('%Y-%m-%dT%H:%M:%S')

    @api.constrains('discount')
    def _check_value(self):
        for invoice_line in self:
            if invoice_line.discount < 0 or invoice_line.discount > 100:
                raise UserError('O valor do desconto deve estar entre 0% e 100%.')
        return True

    def unlink(self):
        for line in self:
            if line.move_id.state != 'draft' or \
                    (
                            line.move_id.state == 'cancel' and not line.move_id.internal_number and not line.move_id.hash):
                raise ValidationError(
                    _('Aviso\n Apenas é possível eliminar documentos no estado de rascunho.'))
        return super(AccountMoveLine, self).unlink()

    @api.onchange('tax_ids')
    def _onchange_invoice_line_tax_ids(self):
        for invoice_line in self:
            if len(invoice_line.tax_ids) >= 2:
                warning_mess = {
                    'title': _('Atenção!'),
                    'message': _('Está a utilizar mais do que um imposto!')}
                return {'warning': warning_mess}
