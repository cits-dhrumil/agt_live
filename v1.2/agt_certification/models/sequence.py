# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import fields, models, api, _


class IrSequenceDateRange(models.Model):
    _inherit = "ir.sequence.date_range"

    codigo_validacao_serie = fields.Char(string="Validation Code",
                             copy=False)

class IrSequence(models.Model):
    _inherit = "ir.sequence"

    implementation = fields.Selection([('standard', 'Standard'), ('no_gap', 'No gap')],
                                      string='Implementation', required=True, default='no_gap',
                                      )
    codigo_validacao_serie = fields.Char(string="Validation Code", copy=False)

    @api.model
    def create(self, vals):
        if 'prefix' in vals and vals['prefix']:
            while vals['prefix'].count('/') > 1:
                pos = vals['prefix'].find('/')
                vals['prefix'] = _(vals['prefix'][:pos]) + _(vals['prefix'][pos + 1:])

        sequence = super(IrSequence, self).create(vals)

        if 'code' in vals and vals['code'] == 'stock.picking.gd.validate':
            stock_picking_types = self.env['stock.picking.type'].search([('sequence_id_gd_validate', '=', False)])
            for stock_picking_type in stock_picking_types:
                try:
                    stock_picking_type.sequence_id_gd_validate = sequence.id
                except:
                    pass
        elif 'code' in vals:
            code = False
            if 'code' in vals and vals['code'] == 'stock.picking.out.validate':
                code = 'outgoing'
            elif 'code' in vals and vals['code'] == 'stock.picking.in.validate':
                code = 'incoming'
            elif 'code' in vals and vals['code'] == 'stock.picking.internal.validate':
                code = 'internal'
            if code:
                stock_picking_types = self.env['stock.picking.type'].search([('code', '=', code),
                                                                            ('sequence_id_validate', '=', False)])
                for stock_picking_type in stock_picking_types:
                    try:
                        stock_picking_type.sequence_id_validate = sequence.id
                    except:
                        pass

        local_stock = self.env['stock.location'].search([('usage', '=', 'internal')], order='id ASC', limit=1).id
        local_clientes = self.env['stock.location'].search([('usage', '=', 'customer')], order='id ASC', limit=1).id
        local_fornecedores = self.env['stock.location'].search([('usage', '=', 'supplier')], order='id ASC', limit=1).id

        for code, locations in zip(['outgoing', 'incoming', 'internal'],
                                   [[local_stock, local_clientes], [local_fornecedores, local_stock],
                                    [local_stock, local_stock]]):
            for default, local in zip(['default_location_src_id', 'default_location_dest_id'], locations):
                self.env.cr.execute("""
                    SELECT id
                    FROM stock_picking_type
                    WHERE code=%s and coalesce(""" + default + """,0)=0""", (code,))
                stock_location_ids = self.env.cr.fetchall()
                for stock_local_id in stock_location_ids:
                    self.env.cr.execute("""
                        UPDATE stock_picking_type
                        SET """ + default + """=%s
                        WHERE id=%s""", (local, stock_local_id[0]))
        return sequence
