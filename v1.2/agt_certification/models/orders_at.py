# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields


class PedidosAtHistorico(models.Model):
    _name = "pedidos.at.historico"
    _description = 'Histórico dos pedidos AT'
    _order = 'id desc'

    name = fields.Char(string="Document Code", size=64, copy=False)
    at_code = fields.Char(string="AT Code", size=256, copy=False)
    codigo_erro = fields.Char(string="Error code", size=64, copy=False)
    msg_erro = fields.Char(string="Error message", size=512, copy=False)
    doc_state = fields.Char(string="Document state", size=8, copy=False)
    user_id = fields.Many2one('res.users', string="User", required=True, copy=False)
    pedido = fields.Text(string="Order", copy=False)


class UtilizadorFinancas(models.Model):
    _name = "utilizador.financas"
    _description = 'Utilizador das finanças'

    name = fields.Char(string="Permission", size=64, required=True, default="WDT", copy=False)
    user = fields.Char(string="User", size=64, required=True, copy=False)
    passe = fields.Char(string="Password", size=64, required=True, copy=False)
    company_id = fields.Many2one('res.company',
                                 string="Company",
                                 required=True,
                                 default=lambda self: self.env.user.company_id,
                                 copy=False)
    por_defeito = fields.Boolean(string="Autocomplete",
                                 help="Check (tick) if the system is to fill in automatically load date, registration number, etc.",
                                 default=False, copy=False)
    por_defeito_matricula = fields.Char(string="Registration", size=16,
                                        help="Register to use when filling in by default,"
                                             "you can leave it blank.",
                                        copy=False)
    por_defeito_minutos = fields.Integer(string="Additional minutes",
                                         help="Time in minutes to be added to the time at which the guide is validated for the"
                                              "load hour field.",
                                         copy=False)
