# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WizardManualCode(models.TransientModel):
    _name = "wizard.manual.code"
    _description = "Wizard to set new AT code manually in tab"

    name = fields.Char(string="AT Code", size=16, required=True, copy=False)
    at_status = fields.Selection([('insert', 'insert'), ('done', 'done')], string="State",
                                 default="insert", copy=False)
    
    def act_getfile(self):
        if len(self.name) < 9:
            raise UserError(_('O código tem de ser composto por pelo menos 9 dígitos.'))

        if self.env.context.get('active_id'):
            picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
            if picking.at_status != 'success':
                self.env.cr.execute("""
                    UPDATE stock_picking
                    SET at_code=%s, at_status='success'
                    WHERE id=%s""", (self.name, self.env.context.get('active_id')))

        return {'type': 'ir.actions.act_window_close'}

    def act_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
