# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api, _


class WizardAlterarGuia(models.TransientModel):
    _name = "wizard.alterar.guia"
    _description = "Wizard to change fields in the tab after it has been validated and whose AT status is canceled"

    name = fields.Char(string="Vehicle: ", size=16, help='Matrícula', copy=False)
    data_carga = fields.Datetime(string="Load date", copy=False)
    data_descarga = fields.Datetime(string="Discharge date", copy=False)

    def act_getfile(self):
        if self.env.context.get('active_id'):
            picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))
            number = picking.name
            picking_type = self.env['stock.picking.type'].search([('id', '=', picking.picking_type_id.id)]).code
            if picking_type and picking.at_status == 'cancel':
                model_list = {
                    'out': 'stock.picking.out',
                    'in': 'stock.picking.in',
                    'internal': 'stock.picking',
                }
                picking_obj = self.env['stock.picking'].browse(self.env.context['active_id'])
                new_picking = picking_obj.copy({'type': 'internal'})

                if self.name is not False:
                    self.env.cr.execute("""
                        UPDATE stock_picking
                        SET veiculo=%s
                        WHERE id=%s""", (self.name, new_picking.id))
                if self.data_carga:
                    self.env.cr.execute("""
                        UPDATE stock_picking
                        SET data_carga=%s
                        WHERE id=%s""", (self.data_carga, new_picking.id))
                if self.data_descarga:
                    self.env.cr.execute("""
                        UPDATE stock_picking
                        SET data_descarga=%s
                        WHERE id=%s""", (self.data_descarga, new_picking.id))

                stock_move = self.env['stock.move'].search([('picking_id', '=', new_picking.id)])
                if stock_move:
                    number = str(stock_move.order_references) + ";" + str(number)

                self.env.cr.execute("""
                    UPDATE stock_move
                    SET order_references=%s
                    WHERE picking_id=%s""", (number, new_picking.id))

                return {
                    'domain': "[('id', 'in', [" + str(new_picking.id) + "])]",
                    'name': _('Returned Picking'),
                    'view_type': 'form',
                    'view_mode': 'tree,form',
                    'res_model': model_list.get(picking_type, 'stock.picking'),
                    'type': 'ir.actions.act_window',
                    'context': self.env.context,
                }

        return {'type': 'ir.actions.act_window_close'}

    def act_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
