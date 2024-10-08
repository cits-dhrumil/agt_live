# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from datetime import datetime
from pytz import timezone
from . import creating_hash
from . import qr_code_generation

tz_pt = timezone('Europe/Lisbon')


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _get_sequence_for_atcud(self):
        for payment in self:
            return payment.journal_id.sequence_id

    def _get_qr_code_generation(self):
        for payment in self:
            payment.qr_code_at = ''
            if payment.hash:
                nif_empresa = payment.company_id.vat
                nif_cliente = payment.partner_id.commercial_partner_id and payment.partner_id.commercial_partner_id.vat or \
                              payment.partner_id.vat
                pais_cliente = payment.partner_id.commercial_partner_id and payment.partner_id.commercial_partner_id.country_id and \
                               payment.partner_id.commercial_partner_id.country_id.code or (payment.partner_id.country_id and \
                                                                                         payment.partner_id.country_id.code or 'PT')
                wizard_atcud = self.env['alert.atcud']
                tipo_documento = wizard_atcud.get_tipo_documento_from_sequence(self._get_sequence_for_atcud())
                doc_state = 'N'
                if payment.state == 'cancel':
                    doc_state = 'A'
                doc_date = payment.date
                numero = payment.name
                atcud = payment.atcud
                espaco_fiscal = '0'

                valor_base_isento = 0
                valor_base_red = 0
                valor_iva_red = 0
                valor_base_int = 0
                valor_iva_int = 0
                valor_base_normal = 0
                valor_iva_normal = 0
                valor_n_sujeito_iva = 0
                imposto_selo = 0
                retencao_na_fonte = 0

                total_impostos = 0.00
                total_com_impostos = 0.00

                quatro_caratecters_hash = _(payment.hash[0:1]) + _(payment.hash[10:11]) + _(payment.hash[20:21]) + \
                                          _(payment.hash[30:31])
                n_certificado = '1456'
                outras_infos = ''

                payment.qr_code_at = qr_code_generation.qr_code_at(nif_empresa, nif_cliente, pais_cliente, tipo_documento,
                                                                doc_state, doc_date, numero, atcud, espaco_fiscal,
                                                                round(valor_base_isento, 2),
                                                                round(valor_base_red, 2),
                                                                round(valor_iva_red, 2),
                                                                round(valor_base_int, 2),
                                                                round(valor_iva_int, 2),
                                                                round(valor_base_normal, 2),
                                                                round(valor_iva_normal, 2),
                                                                round(valor_n_sujeito_iva, 2),
                                                                round(imposto_selo, 2),
                                                                round(total_impostos, 2),
                                                                round(total_com_impostos, 2),
                                                                round(retencao_na_fonte, 2),
                                                                quatro_caratecters_hash,
                                                                n_certificado, outras_infos)

    def _compute_atcud(self):
        for payment in self:
            payment.atcud = ''
            needs_atcud = self.env['ir.config_parameter'].sudo().get_param('needs_atcud')
            if payment.hash and needs_atcud == 'True':
                wizard_atcud = self.env['alert.atcud']
                sequence_id = payment._get_sequence_for_atcud()
                codigo_validacao_serie = wizard_atcud._get_codigo_validacao_serie(sequence_id, payment.date)
                if codigo_validacao_serie:
                    n_sequencial_serie = payment.name.split('/')[1]
                    payment.atcud = _(codigo_validacao_serie) + '-' + n_sequencial_serie

    def validar_hash(self):
        for payment in self:
            ano = datetime.now().year
            if payment.date:
                ano = payment.date.year
            data_inicio = '01-01-' + str(ano)
            data_inicio = datetime.strptime(data_inicio, '%d-%m-%Y')
            data_fim = '31-12-' + str(ano)
            data_fim = datetime.strptime(data_fim, '%d-%m-%Y')
            numHash = self.env['account.payment'].search_count([
                ('partner_type', '=', payment.partner_type),
                ('id', '!=', payment.id),
                ('journal_id', '=', payment.journal_id.id),
                ('date', '<=', data_fim),
                ('date', '>=', data_inicio),
                ('hash', '!=', False),
                ('state', '=', 'posted')
            ])
            antigoHash = False
            if numHash > 0:
                antigoHash = self.env['account.payment'].search([
                    ('partner_type', '=', payment.partner_type),
                    ('id', '!=', payment.id),
                    ('journal_id', '=', payment.journal_id.id),
                    ('date', '<=', data_fim),
                    ('date', '>=', data_inicio),
                    ('state', '=', 'posted'),
                    ('hash', '!=', False),
                ], order='id desc', limit=1).hash
            return numHash, antigoHash

    hash = fields.Char(string="Hash", size=256, readonly=True, help="Unique hash of the sale order.", copy=False)
    hash_control = fields.Char(string="Key", size=40, copy=False)
    hash_date = fields.Datetime(string="Date the hash was generated", copy=False)
    atcud = fields.Char(compute='_compute_atcud', string='ATCUD')
    qr_code_at = fields.Char(compute='_get_qr_code_generation', string='QR Code AT')
    qr_code_at_img = fields.Binary("QR Code", compute='_compute_qr_code_image')
    outstanding_account_id = fields.Many2one(
        comodel_name='account.account',
        string="Outstanding Account",
        store=True,
        compute='_compute_outstanding_account_id',
        check_company=True)
    payment_mechanism = fields.Selection([('CC', 'Credit Card'),
                                          ('CD', 'Debit Card'),
                                          ('CH', 'Bank check'),
                                          ('CO', 'Check or gift card'),
                                          ('CS', 'Clearance of current account balances'),
                                          ('DE', 'Electronic money, for example resident on loyalty or points cards'),
                                          ('LC', 'Business letter'),
                                          ('MB', 'ATM payment references'),
                                          ('NU', 'Cash'),
                                          ('OU', 'Other means not indicated here'),
                                          ('PR', 'Exchange of goods'),
                                          ('TB', 'Bank transfer or direct debit authorized'),
                                          ('TR', 'Restaurant Ticket'), ], string="Meio de pagamento", required=True,
                                         readonly=True, default='NU', copy=False)

    def _compute_qr_code_image(self):
        for payment in self:
            payment.qr_code_at_img = self.env['alert.atcud']._compute_qr_code_image(payment.qr_code_at)

    @api.depends('journal_id', 'payment_type', 'payment_method_line_id')
    def _compute_outstanding_account_id(self):
        for pay in self:
            if pay.journal_id.default_account_id:
                pay.outstanding_account_id = pay.journal_id.default_account_id.id
            else:
                pay.outstanding_account_id = False

    def action_post(self):
        for payment in self:
            if not payment.company_id.pais_certificacao or payment.company_id.pais_certificacao.code == 'PT':
                if payment.payment_type == 'inbound':
                    # ATCUD#
                    needs_atcud = self.env['ir.config_parameter'].sudo().get_param('needs_atcud')
                    if needs_atcud == 'True':
                        wizard_alert_atcud = self.env['alert.atcud']
                        sequence_id_atcud = payment._get_sequence_for_atcud()
                        if not sequence_id_atcud:
                            raise UserError(_(u'Sequencia não encontrada'))
                        codigo_validacao_serie = wizard_alert_atcud._get_codigo_validacao_serie(sequence_id_atcud,
                                                                                                payment.date)
                        if not codigo_validacao_serie:
                            if self.env.company.series_at_user and self.env.company.series_at_password:
                                # consult if the series has been registered in the AT platform. Register if not.
                                result = self.env['res.config.settings'].register_automatically(sequences=sequence_id_atcud)
                                self.env['series.wizard.registration.result'].search([('id', '=', result['res_id'])]).evaluate_summary()
                                new_code = wizard_alert_atcud._get_codigo_validacao_serie(sequence_id_atcud,
                                                                                          payment.date)
                                payment.message_post(body=_('Foi atribuído o código de validação de sequência AT: %s' % new_code))
                            else:
                                if self.env.user.has_group('account.group_account_manager'):
                                    action = self.env.ref('base_setup.action_general_configuration')
                                    wizard_alert_atcud.treat_sequences()
                                    msg = _(
                                        'Falta definir o codigo de validação de sequência AT e o user AT para este efeito.'
                                        '\nPor favor registe o seu Utilizador de Comunicação de Séries em Definições, ou '
                                        ' clique no link abaixo.')
                                    raise RedirectWarning(msg, action.id, _('Configurar Utilizador AT'))
                                else:
                                    raise UserError(_(
                                        'Falta definir o codigo de validação de sequência AT. Para configurar, '
                                        'deverá aceder ao menu Faturação -> Configuração -> Configurar ATCUD'))
            if payment.partner_id and not payment.journal_id.predatado and payment.payment_type == 'inbound':
                payment.create_hash()
        return super(AccountPayment, payment).action_post()

    def create_hash(self):
        for payment in self:
            datasistema = str(payment.write_date)[:19]
            datadocumento = payment.date
            numHash, antigoHash = payment.validar_hash()
            totalbruto = str(payment.amount)
            if (totalbruto.find('.') + 2) == len(totalbruto):
                totalbruto += "0"
            number = payment.journal_id.saft_inv_type + ' ' + payment.name and payment.name or ''
            values = creating_hash.hash(self, payment.journal_id.manual, datadocumento,
                                          datasistema, number, numHash, antigoHash, totalbruto)
            payment.write(values)

    def unlink(self):
        if any(rec.hash != False and rec.partner_type != 'supplier' for rec in self):
            raise UserError(_("Não pode apagar um pagamento que já tenha sido validado!"))

        if any(rec.state != 'draft' and rec.payment_type == 'inbound' for rec in self):
            raise UserError(_(u'Não pode eliminar pagamentos que não sejam rascunhos.'))
        return super(AccountPayment, self).unlink()
