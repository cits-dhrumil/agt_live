# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api


class TipoProdutoSaft(models.Model):
    _name = "tipo.produto.saft"
    _description = "Types of products according to the options in the exportable stock file for AT"

    name = fields.Char(string="Name")
    code = fields.Char(string="code")

    _sql_constraints = [('code_unique', 'unique(code)', 'Código deve ser único!')]

    @api.model
    def create(self, vals):
        tipoproduto_saft = super(TipoProdutoSaft, self).create(vals)
        if 'code' in vals and vals['code'] == 'M':
            produtos = self.env['product.template'].search(['|', ('active', '=', True),
                                                            ('active', '=', False),
                                                            ('tipo_produto_id', '=', False),
                                                            ('type', '!=', 'service')])
            for produto in produtos:
                produto.tipo_produto_id = tipoproduto_saft.id

        return tipoproduto_saft
