# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


prefixo_journal_type = {'cash': 'CSH', 'bank': 'BNK', 'sale': 'VD', 'purchase': 'CP', 'general': 'DIV'}


class AccountJournal(models.Model):
    _inherit = "account.journal"

    sequence_id = fields.Many2one('ir.sequence', string='Entry Sequence',
                                  help="This field contains the information related to the numbering of the journal entries of this journal.",
                                  copy=False)
    refund_sequence_id = fields.Many2one('ir.sequence', string='Credit Note Entry Sequence',
                                         help="This field contains the information related to the numbering of the credit note entries of this journal.",
                                         copy=False)
    sequence_number_next = fields.Integer(string='Next Number',
                                          help='The next sequence number will be used for the next invoice.',
                                          compute='_compute_seq_number_next',
                                          inverse='_inverse_seq_number_next')
    refund_sequence_number_next = fields.Integer(string='Credit Notes Next Number',
                                                 help='The next sequence number will be used for the next credit note.',
                                                 compute='_compute_refund_seq_number_next',
                                                 inverse='_inverse_refund_seq_number_next')
    self_billing = fields.Boolean(string="Self-Invoicing",
                                  copy=False)
    transaction_type = fields.Selection([('N', 'Normal'),
                                         ('R', 'Regularizations'),
                                         ('A', 'Apur. Results'),
                                         ('J', 'Adjustments')],
                                        string="Release Type",

                                        default="N",
                                        copy=False)
    saft_inv_type = fields.Selection([('FT', 'Invoice'),
                                      ('FR', 'Invoice Receipt'),
                                      ('ND', 'Debit note'),
                                      ('VD', 'Cash Sale'),
                                      ('AA', 'Asset Disposal'),
                                      ('DA', 'Return of Assets'),
                                      ('FS', 'Simplified Invoice'),
                                      ('receipt', 'Receipt'),
                                      ('payment', 'Payment')],
                                     string="Document Type",
                                     help="Categories to classify commercial documents when exporting SAFT",
                                     default="FT",
                                     copy=False)
    por_defeito = fields.Boolean(string="Default journal", copy=False)
    manual = fields.Boolean(string="Manual Billing", copy=False)
    integrado = fields.Boolean(string="Integrated", help="Integrated documents from another application", copy=False)
    predatado = fields.Boolean(string="Pre-dated", help="If you give the visa, these receipts will not appear in the saft, and will not be hashed", copy=False)
    paga_me = fields.Boolean(string="Automatic Payment",
                             help="Select this if you want invoices in the VD Diary to be automatically paid",
                             default=False, copy=False)
    allow_date = fields.Boolean(string="Check Period", default=True, copy=False)
    refund_sequence = fields.Boolean(string='Dedicated Credit Note Sequence',
                                     help="Check this box if you don't want to share the same sequence for invoices and "
                                          "credit notes made from this journal", default=True)

    # do not depend on 'sequence_id.date_range_ids', because
    # sequence_id._get_current_sequence() may invalidate it!
    @api.depends('sequence_id.use_date_range', 'sequence_id.number_next_actual')
    def _compute_seq_number_next(self):
        '''Compute 'sequence_number_next' according to the current sequence in use,
        an ir.sequence or an ir.sequence.date_range.
        '''
        for journal in self:
            if journal.sequence_id:
                sequence = journal.sequence_id._get_current_sequence()
                journal.sequence_number_next = sequence.number_next_actual
            else:
                journal.sequence_number_next = 1

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'code' in vals and vals['code']:
                code = vals['code']
            else:
                code = _(vals['name'])[:3]

            if 'sequence_id' not in vals or vals['sequence_id'] is False:
                values_sequence = {'name': _(vals['name']),
                                   'prefix': _(code) + '/'}
                ir_sequence = self.env['ir.sequence'].create(values_sequence)
                vals['sequence_id'] = ir_sequence.id
            if 'refund_sequence_id' not in vals or vals['refund_sequence_id'] is False:
                values_sequence_refund = {'name': vals['name'],
                                          'prefix': 'R' + _(code) + '/'}
                refund_ir_sequence = self.env['ir.sequence'].create(values_sequence_refund)
                vals['refund_sequence_id'] = refund_ir_sequence.id
        return super(AccountJournal, self).create(vals_list)

    def write(self, vals):
        for journal in self:
            if 'predatado' in vals:
                search_moves = self.env['account.move'].search([
                    ('journal_id', '=', journal.id),
                    ('state', '=', 'posted')]
                )
                if len(search_moves) > 0:
                        raise ValidationError('Já existem documentados neste diário, pelo que não pode alterar este campo.')

            if 'manual' in vals or 'integrado' in vals:
                total = self.env['account.payment'].search_count([('journal_id', '=', journal.id)])
                total += self.env['account.move'].search_count([('journal_id', '=', journal.id)])

                if 'manual' in vals and total > 0:
                    raise ValidationError(_('Não pode definir o diário como manual, '
                                            'pois este já entra em faturas ou recibos.'))

                if 'integrado' in vals and total > 0:
                    raise ValidationError(_('Não pode definir o diário como integrado, '
                                            'pois este já entra em faturas ou recibos.'))

        return super(AccountJournal, self).write(vals)

    @api.constrains('code')
    def _check_code(self):
        for journal in self:
            if not journal.code.isalnum():
                journal.code = re.sub('[^A-Za-z0-9]', '', journal.code)

            if len(self.search([('code', '=', journal.code), ('company_id', '=', self.env.company.id),
                                ('id', '!=', journal.id)])) > 0:
                if self.env.context.get('defcopy'):
                    ctx = self.env.context.copy()
                    del ctx['defcopy']
                    journal.code = journal.with_context(ctx).generate_code()
                else:
                    raise ValidationError('Este código já existe noutro diário')
        return True

    # do not depend on 'refund_sequence_id.date_range_ids', because
    # refund_sequence_id._get_current_sequence() may invalidate it!
    @api.depends('refund_sequence_id.use_date_range',
                 'refund_sequence_id.number_next_actual')
    def _compute_refund_seq_number_next(self):
        '''Compute 'sequence_number_next' according to the current sequence in use,
        an ir.sequence or an ir.sequence.date_range.
        '''
        for journal in self:
            if journal.refund_sequence_id and journal.refund_sequence:
                sequence = journal.refund_sequence_id._get_current_sequence()
                journal.refund_sequence_number_next = sequence.number_next_actual
            else:
                journal.refund_sequence_number_next = 1

    @api.constrains('type')
    def _check_type(self):
        for journal in self:
            if journal.type in ['sale', 'purchase'] and not journal.refund_sequence_id:
                raise ValidationError('O diário tem de ter sequência de reembolso')
        return True

    def copy(self, default=None):
        ctx = self.env.context.copy()
        ctx['defcopy'] = True
        return super(AccountJournal, self.with_context(ctx)).copy(default)

    @api.onchange('code')
    def _onchange_code(self):
        for journal in self:
            if journal.code:
                journal.code = re.sub('[^A-Za-z0-9]', '', journal.code)

    def generate_code(self):
        for journal in self:
            if self.search([('code', '=', journal.code), ('company_id', '=', self.env.company.id)]):
                for num in range(1, 100):
                    # journal_code has a maximal size of 5, hence we can enforce the boundary num < 100
                    journal_code = prefixo_journal_type[journal.type] + str(num)
                    if not self.env['account.journal'].search(
                            [('code', '=', journal_code), ('company_id', '=', self.env.company.id)], limit=1):
                        return journal_code
        return journal.code

    def _inverse_seq_number_next(self):
        '''Inverse 'sequence_number_next' to edit the current sequence next number.
        '''
        for journal in self:
            if journal.sequence_id and journal.sequence_number_next:
                sequence = journal.sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.sequence_number_next

    def _inverse_refund_seq_number_next(self):
        '''Inverse 'refund_sequence_number_next' to edit the current sequence next number.
        '''
        for journal in self:
            if journal.refund_sequence_id and journal.refund_sequence and journal.refund_sequence_number_next:
                sequence = journal.refund_sequence_id._get_current_sequence()
                sequence.sudo().number_next = journal.refund_sequence_number_next
