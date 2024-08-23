# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields


class HistSaft(models.Model):
    _name = "hist.saft"
    _description = 'Histórico de SAFT'
    _order = 'data_criacao desc'

    data_criacao = fields.Datetime(string="Creation Date", readonly=True)
    data_inicio = fields.Date(string="Start Date", readonly=True)
    data_fim = fields.Date(string="End Date", readonly=True)
    user = fields.Many2one('res.users', string="Utilizador", readonly=True, default=lambda self: self.env.uid)
    tipo = fields.Selection([('import', 'Import'),
                                       ('export', 'Export')], string="Type", readonly=True)
    state = fields.Selection([('nao_validado', 'Not validated'), ('validado', 'Validated'),
                                        ('submetido', 'Submitted')], string="Status", readonly=True,
                             default="nao_validado")
    empresa = fields.Many2one('res.company', string="Company", readonly=True,
                              default=lambda self: self.env['res.company']._company_default_get('hist.saft'))
    nif = fields.Char(string="NIF", size=64, readonly=True)
    num_faturas = fields.Integer(string="Number of Invoices", readonly=True)
    valor_credito = fields.Char(string="Credit Value", size=64, readonly=True)
    valor_debito = fields.Char(string="Debit Amount", size=64, readonly=True)

    def do_submete(self):
        self.write({'state': 'submetido'})

    def do_valida(self):
        self.write({'state': 'validado'})

    def do_nao_valida(self):
        self.write({'state': 'nao_validado'})
