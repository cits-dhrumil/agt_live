# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api


class IrSequenceAtcud(models.Model):
    _name = "ir.sequence.atcud"

    sequence_id = fields.Many2one('ir.sequence', string="Sequence", readonly=True)
    codigo_validacao_serie = fields.Char(string="Validation Code",
                                          readonly=True)
    identificador_serie = fields.Char(string="Series Identifier", readonly=True)
    inicio_numeracao = fields.Char(string="Start of Numbering", readonly=True)
    tipo_documento = fields.Char(string="Document Type", readonly=True)

    
    def open_wizard(self):
        for seqs in self:
            action = self.env.ref('agt_certification.action_wizard_alert_atcud').read()[0]
            action['views'] = [(False, 'form')]
            action['context'] = {'default_hide': '1',
                                 'default_sequence_id': seqs.sequence_id.id,
                                 'default_codigo_validacao_serie': seqs.codigo_validacao_serie,
                                 'default_identificador_serie': seqs.identificador_serie,
                                 'default_inicio_numeracao': seqs.inicio_numeracao,
                                 'default_tipo_documento': seqs.tipo_documento,
                                 }
            return action