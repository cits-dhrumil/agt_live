# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################
import logging
import datetime
from datetime import datetime, date
from pytz import timezone
from dateutil.relativedelta import relativedelta
from . import creating_hash
from odoo import models, fields, api, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from functools import partial
from odoo.tools.misc import formatLang
from . import qr_code_generation

_logger = logging.getLogger(__name__)

# mapping invoice type to journal type
TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale',
    'in_refund': 'purchase',
}

# mapping invoice type to refund type
TYPE2REFUND = {
    'out_invoice': 'out_refund',  # Customer Invoice
    'in_invoice': 'in_refund',  # Supplier Invoice
    'out_refund': 'out_invoice',  # Customer Refund
    'in_refund': 'in_invoice',  # Supplier Refund
}

# Tipo usado para devoluções
TYPE2PICKING = {
    'out_invoice': 'incoming',  # Customer Invoice
    'in_invoice': 'outgoing',
}

MAGIC_COLUMNS = ('id', 'create_uid', 'create_date', 'write_uid', 'write_date')

tz_pt = timezone('Europe/Lisbon')


class AccountMove(models.Model):
    _inherit = "account.move"

    def grosstotal(self):
        integer, decimal = str(self.amount_total).split('.')
        return '.'.join([integer, decimal.ljust(2, '0')])

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if 'currency_id' in values and values['currency_id'] and \
                    values['currency_id'] != self.env.company.currency_id.id:
                date_fatura = datetime.now()
                data_inicial = str(date_fatura)[:10] + ' 00:00:00'
                data_final = str(date_fatura)[:10] + ' 23:59:59'
                # get taxa de cambio para a data da fatura
                rate = self.env['res.currency.rate'].search([
                    ('currency_id', '=', values['currency_id']),
                    ('name', '>=', data_inicial),
                    ('name', '<=', data_final)], order='name desc', limit=1)
                values['cambio'] = rate.rate or '1'
        return super(AccountMove, self).create(vals_list)

    def copy(self, default=None):
        ctx = self.env.context.copy()
        # se a moeda da fatura for diferente da moeda da empresa, entao preenche o campo
        if self.currency_id and self.currency_id != self.company_id.currency_id:
            date_fatura = datetime.now()
            if self.date:
                date_fatura = self.date
            data_inicial = str(date_fatura)[:10] + ' 00:00:00'
            data_final = str(date_fatura)[:10] + ' 23:59:59'
            # get taxa de cambio para a data da fatura
            rate = self.env['res.currency.rate'].search([
                ('currency_id', '=', self.currency_id.id),
                ('name', '>=', data_inicial),
                ('name', '<=', data_final)], order='name desc', limit=1)
            self.cambio = rate.rate or '1'
        else:
            self.cambio = 1
        return super(AccountMove, self.with_context(ctx)).copy(default)

    # metodo de tratamento do cambio e mensagem de alertas sobre o cambio na fatura
    @api.depends('currency_id', 'cambio')
    def _get_currency_tax_info(self):
        for invoice in self:
            invoice.currency_tax_info = ''
            # se a moeda da fatura for diferente da moeda da empresa, entao preenche o campo
            if invoice.currency_id and invoice.currency_id != invoice.company_id.currency_id:
                date_fatura = datetime.now()
                if invoice.invoice_date:
                    date_fatura = self.invoice_date
                data_inicial = str(date_fatura)[:10] + ' 00:00:00'
                data_final = str(date_fatura)[:10] + ' 23:59:59'
                # get taxa de cambio para a data da fatura
                rate = self.env['res.currency.rate'].search([
                    ('currency_id', '=', invoice.currency_id.id),
                    ('name', '>=', data_inicial),
                    ('name', '<=', data_final)], order='name desc', limit=1)

                if rate and rate.rate and rate.name:
                    if invoice.state == 'draft':
                        data = str(rate.name)[:10]
                        invoice.cambio = rate.rate
                        invoice.currency_tax_info = 'Taxa de câmbio de ' + str(rate.rate) + ' do dia ' + str(data) + '.'
                if invoice.state != 'draft':
                    invoice.currency_tax_info = str(invoice.cambio or '1')

    # metodo para mostrar cambio ou esconder
    @api.depends('currency_id', 'company_id')
    def _get_moeda_show(self):
        for invoice in self:
            invoice.moeda_show = False
            if invoice.currency_id != invoice.company_id.currency_id:
                invoice.moeda_show = True

    # metodo para trazer dados do cliente para a fatura
    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        result = super(AccountMove, self)._onchange_partner_id()
        for invoice in self:
            # Se o parceiro tem um vendedor ele será associado à fatura caso contrario então o vendedor é o utilizador
            if invoice.partner_id and invoice.partner_id.user_id and invoice.partner_id.user_id.id:
                invoice.user_id = invoice.partner_id.user_id.id
            else:
                invoice.user_id = self.env.uid
        return result

    # valicoes dados cliente
    def verificar_cliente_data(self):
        for invoice in self:
            if invoice.move_type in ('out_invoice', 'out_refund'):
                if not invoice.partner_id.name and not invoice.partner_id.parent_id:
                    raise UserError(_('O parceiro não possui nome!'))
                # verificar se o mes não é o proximo
                if str(invoice.invoice_date) >= (datetime(datetime.now(tz_pt).year, datetime.now(tz_pt).month, 1) +
                                                 relativedelta(months=1)).strftime('%Y-%m-%d'):
                    raise UserError('O mês da fatura tem de ser o mês corrente ou inferior.')
                    # fim validar mes

                # Verificação do ano
                if invoice.journal_id.allow_date and invoice.invoice_date.year < datetime.now(tz_pt).year:
                    raise UserError(_('Não pode validar para anos anteriores ao corrente.'))

                # verifica se a data e menor
                # Informacao recolhida da AT - Sr. Constantino:
                # Relativamente à questão que coloca,e, na minha opinião, a data do documento seguinte da mesma série,
                # nunca poderá ser inferior à do último emitido, independentemente do "Status" do documento.
                # A validação que a aplicação faz sobre o controlo das datas dos documentos emitidos faz 100% de sentido,
                # caso contrário, o artigo 36º do CIVA pode ficar prejudicado, nomeadamente o seu nº 5.
                # Como alternativa, poderá considerar a criação de uma nova série.
                if not invoice.journal_id.integrado:
                    self.env.cr.execute("""
                        SELECT max(invoice_date)
                        FROM account_move
                        WHERE state != 'draft' and move_type=%s and journal_id = %s""",
                                        (invoice.move_type, invoice.journal_id.id))
                    max_date = self.env.cr.fetchone()[0]
                    if max_date and invoice.invoice_date < max_date:
                        raise UserError(
                            _('A data do documento nao pode ser inferior a data de documentos validados anteriormente.'))
        return True

    # Definir a sequência como "Sem Espaços"
    def validar_sequencia_moeda(self):
        for invoice in self:
            if invoice.journal_id.sequence_id.implementation != 'no_gap':
                raise UserError(_('Erro!\n Deve definir a sequência como "Sem Espaços".'))
            # verificar se a moeda e igual a da empresa e se nao for, get cambio actual para a fatura.
            if invoice.company_id.currency_id and invoice.company_id.currency_id != invoice.currency_id:
                # se a data da fatura tiver preenchida tenho de olhar para essa data, se nao tiver preenchida uso o datetime.now com o timezone
                date_fatura = datetime.now(tz_pt)
                if invoice.invoice_date:
                    date_fatura = invoice.invoice_date
                # verificar se o cambio é 1
                currency_rate = self.env['res.currency.rate'].search([
                    ('currency_id', '=', invoice.currency_id.id),
                    ('name', '>=', str(date_fatura)[:10] + ' 00:00:00'),
                    ('name', '<=', str(date_fatura)[:10] + ' 23:59:59')], order='name DESC', limit=1)
                if currency_rate:
                    if round(currency_rate.rate, 5) != round(invoice.cambio, 5) and invoice.move_type not in (
                    'out_refund', 'in_refund'):
                        raise ValidationError(
                            'Deve definir uma taxa de câmbio para a data e moeda definidas na fatura!')
                else:
                    raise ValidationError('Deve definir uma taxa de câmbio para a data e moeda definidas na fatura!')

        # na NC a fatura n pode estar cancelada
        if invoice.move_type == 'out_refund' and invoice.invoice_origin:
            int_numb = _(invoice.invoice_origin)
            diario_pre = False
            if int_numb.find(" ") != -1:
                int_numb = int_numb.split(" ")
                diario_pre = int_numb[0]
                int_numb = int_numb[1]

            fatura_da_nota_crediro = self.search([('internal_number', '=', int_numb)])
            if fatura_da_nota_crediro.state == 'cancel':
                if diario_pre:
                    if fatura_da_nota_crediro.journal_id.saft_inv_type == diario_pre:
                        raise ValidationError(_('Incorreto !\n A Fatura que está no doc. de origem da Nota de Crédito '
                                                'já foi cancelada.'))
                else:
                    raise ValidationError(_('Incorreto !\n'
                                            'A Fatura que está no doc. de origem da Nota de Crédito já foi cancelada.'))

    # validacoes nas linhas da fatura
    def verificar_linhas_fatura(self, type_tax_use):
        for invoice in self:
            tax_amount = 0
            lines_count = 0
            for invoice_line in invoice.invoice_line_ids:
                lines_count += 1
                # validacao do valor base de impsto
                for line in invoice.invoice_line_ids:
                    price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
                    taxes = line.tax_ids.compute_all(price_reduce, quantity=line.quantity, product=line.product_id,
                                                     partner=invoice.partner_id)['taxes']
                    for tax in line.tax_ids:
                        for t in taxes:
                            if t['id'] == tax.id or t['id'] in tax.children_tax_ids.ids:
                                tax_amount += t['amount']

                if invoice_line.display_type and invoice_line.display_type == 'product':
                    if not invoice_line.product_id:
                        raise ValidationError('Incompleto !\n Todas as linhas da fatura tem de ter produto.')
                    if invoice_line.product_uom_id.id is False:
                        raise ValidationError(
                            'Incompleto !\n Todas as linhas da fatura tem de possuir unidade de medida.')
                    if not invoice_line.tax_ids:
                        raise ValidationError('Incompleto !\n Todas as linhas da fatura tem de possuir imposto.')
                    iva_tax_found = any(tax.saft_tax_type == 'IVA' for tax in invoice_line.tax_ids)
                    if not iva_tax_found:
                        raise ValidationError("At least one tax must have saft_tax_type == IVA.")
                    for tax in invoice_line.tax_ids:
                        if tax.type_tax_use != type_tax_use:
                            raise ValidationError(
                                'Erro !\n O imposto em documentos de Clientes tem que ser do tipo "Venda" '
                                'e em documentos de Fornecedores tem que ser do tipo "Compra".')

    # validacoes diarios da fatura
    def verificar_diarios(self):
        for invoice in self:
            # se for documento manual tem de preencher o campo documento de origem
            if invoice.journal_id and not invoice.invoice_origin and invoice.journal_id.manual is True:
                raise ValidationError('Erro na Data !\n Nos documentos manuais tem de ser indicado '
                                      'o numero do documento de origem na aba "Outras Informacoes".')
            # nao permitir diarios VD
            if invoice.journal_id.saft_inv_type == 'VD':
                raise ValidationError('Incompleto !\n Nao pode usar Vendas a Dinheiro.')

            # Origin obrigatorio if NC ou ND
            if invoice.journal_id.saft_inv_type in ['NC', 'ND'] and not invoice.invoice_origin:
                raise ValidationError('Incompleto !\n Com diario selecionado, o campo Doc. Origem na fatura '
                                      'tem de ser preenchido.')

            # verificar se é de pagamento automatico
            if invoice.journal_id.paga_me:
                if invoice.journal_id.saft_inv_type == 'FR' and invoice.amount_total == 0:
                    raise ValidationError('Atenção !\n Não pode validar uma Fatura Recibo com valor 0.')

                if not invoice.ref_pagamento or invoice.ref_pagamento == '---':
                    raise ValidationError(
                        'Incompleto !\n Necessita de preencher o campo referencia do pagamento quando utiliza esse diario.')

    def verificar_dados_fatura(self):
        for invoice in self:
            if invoice.move_type == 'out_refund' and (not invoice.reason_cancel or not invoice.invoice_origin):
                raise ValidationError(_('Incompleto\n'
                                        'Os campos "Origem" e "Motivo de Anulação" são de preenchimento obrigatório.'))

            # verificar se para aquele fornecedor ja existe um referencia igual noutra fatura
            if invoice.partner_id and self.move_type in ['in_invoice', 'in_refund'] and invoice.ref:
                self.env.cr.execute("""
                            SELECT ref
                            FROM account_move
                            WHERE state not in ('draft','cancel') and
                                  move_type=%s and internal_number!='/'
                                  and ref=%s and partner_id=%s and id != %s """, (invoice.move_type, invoice.ref,
                                                                                  invoice.partner_id.id, invoice.id))
                check_internal_number = self.env.cr.fetchone()
                if check_internal_number:
                    raise ValidationError('Duplicado !\n Ja existe uma fatura (' + str(
                        check_internal_number[0]) + ') para esse fornecedor com essa referencia!')
            # n pode validar a nota de credito se a fatura estiver cancelada
            if invoice.move_type == 'in_refund' and invoice.invoice_origin:
                self.env.cr.execute(
                    "SELECT state FROM account_move where internal_number='" + invoice.invoice_origin + "'")
                state_origign = self.env.cr.fetchone()
                if state_origign and state_origign[0] == 'cancel':
                    raise ValidationError('Restrição !\n A fatura de origem está no estado cancelado '
                                          'pelo que não pode validar a nota de crédito.')
            # verificar se o documento tem um total negativo
            if invoice.amount_total < 0:
                raise ValidationError(_('Impossibilidade\n Nao pode validar faturas com um total negativo!'))
            if invoice.name.count("/") != 1 and invoice.move_type in ('out_invoice', 'out_refund'):
                raise ValidationError('Config\n O numero tem de ter apenas uma barra.')
            if not invoice.journal_id.refund_sequence and invoice.move_type in ('out_refund', 'in_refund'):
                raise ValidationError('Config\n Deve definir o visto no campo Sequencia de Reembolso Dedicada no '
                                      'diario selecionado antes de validar Notas de Credito!')
            if invoice.journal_id.integrado and not invoice.origin_document_status:
                raise ValidationError('O campo Estado Doc. Oiginal é obrigatório.')
            # give a raise if tax is zero and the exemption reason field on tax is not filled
            for line in invoice.invoice_line_ids:
                for tax in line.tax_ids:
                    if tax.amount == 0 and not tax.exemption_reason:
                        raise ValidationError(_('Incompleto\n'
                                                'O imposto ' + tax.name + ' tem valor 0 e não tem motivo de isenção '
                                                                          'preenchido!'))
                    if tax.amount == 0 and tax.exemption_reason and tax.exemption_reason.discontinued:
                        raise ValidationError(_('Erro\n'
                                                'O motivo de isenção ' + tax.exemption_reason.name + ' está descontinuado!'))

    # def validar_hash(self):
    #     # Todo Optimise this code
    #     for invoice in self:
    #         # verificar se é a primeira factura ou nota de credito
    #         if invoice.move_type in ['out_invoice', 'in_invoice']:
    #             code = invoice.journal_id.sequence_id.code + '%%'
    #         else:
    #             code = 'NC.%%'
    #         self.env.cr.execute("""
    #                SELECT COUNT(i.id)
    #                FROM account_move i
    #                WHERE i.move_type=%s and extract(year from invoice_date)=%s and
    #                    i.internal_number != '' and i.hash!='' and
    #                    id!=%s and i.journal_id = %s and i.internal_number LIKE %s """,
    #                             (invoice.move_type, invoice.invoice_date.year,
    #                              invoice.id, invoice.journal_id.id, code))
    #         numHash = self.env.cr.fetchone()[0]
    #         # Se não for a primeira factura ou nota de encomenda vai buscar o hash anterior
    #         antigoHash = False
    #         if numHash > 0:
    #             self.env.cr.execute("""
    #                    SELECT ai.hash,ai.id
    #                    FROM account_move ai, (
    #                        select max(internal_number)
    #                        from account_move
    #                        where hash!='' and  move_type=%s and journal_id =%s and id!=%s and internal_number LIKE %s) mai
    #                    WHERE ai.move_type=%s and ai.internal_number != '' and ai.internal_number = mai.max""",
    #                                 (invoice.move_type, invoice.journal_id.id,
    #                                  invoice.id, code, invoice.move_type))
    #             antigoHash = self.env.cr.fetchone()[0]
    #         return numHash, antigoHash

    def validar_hash(self):
        # Todo Optimise this code
        for invoice in self:
            # verificar se é a primeira factura ou nota de credito
            if invoice.move_type in ['out_invoice', 'in_invoice']:
                code = invoice.journal_id.sequence_id.code + '%%'
            else:
                code = invoice.journal_id.refund_sequence_id.code + '%%'
            params = (
            invoice.move_type, invoice.invoice_date.year, invoice.id, code)
            query = """
                SELECT COUNT(i.id)
                FROM account_move i
                WHERE i.move_type=%s AND extract(year FROM invoice_date)=%s
                AND i.internal_number != '' AND i.hash != ''
                AND id != %s AND i.internal_number LIKE %s"""

            if invoice.move_type != 'out_refund':
                query += " AND i.journal_id = %s"
                params += (invoice.journal_id.id,)

            self.env.cr.execute(query, params)
            numHash = self.env.cr.fetchone()[0]
            antigoHash = False
            if numHash > 0:
                query_prev_hash = """
                    SELECT ai.hash
                    FROM account_move ai, (
                        SELECT max(internal_number) AS max
                        FROM account_move
                        WHERE hash != '' AND move_type=%s AND id != %s
                        AND internal_number LIKE %s"""

                if invoice.move_type != 'out_refund':
                    query_prev_hash += " AND journal_id = %s"
                    params_prev_hash = (
                    invoice.move_type, invoice.id, code, invoice.journal_id.id)
                else:
                    params_prev_hash = (invoice.move_type, invoice.id, code)

                query_prev_hash += ") mai WHERE ai.internal_number = mai.max"

                self.env.cr.execute(query_prev_hash, params_prev_hash)
                antigoHash = self.env.cr.fetchone()[0]

            return numHash, antigoHash

    def create_hash(self):
        '''Need to make dynamic this code for prefix'''
        for invoice in self:
            datasistema = str(datetime.now())[:19]
            datadocumento = invoice.invoice_date
            numHash, antigoHash = invoice.validar_hash()
            totalbruto = float(invoice.amount_total)
            # number = invoice.journal_id.saft_inv_type + ' ' + invoice.name
            number = ((invoice.journal_id.saft_inv_type + ' ') if invoice.move_type not in [
                'out_refund', 'in_refund'] else (
                'NC ' if invoice.move_type == 'out_refund' else 'ND ')) + invoice.name
            values = creating_hash.hash(invoice, invoice.journal_id.manual, datadocumento,
                                          datasistema, number, numHash, antigoHash, totalbruto)
            invoice.write(values)

    def treat_atcud(self):
        for invoice in self:
            # ATCUD#
            if not invoice.company_id.pais_certificacao or invoice.company_id.pais_certificacao.code == 'PT':
                invoice.atcud = ''
                if invoice.move_type in ('out_invoice', 'out_refund'):
                    needs_atcud = self.env['ir.config_parameter'].sudo().get_param('needs_atcud')
                    if not invoice.atcud and needs_atcud == 'True':
                        wizard_alert_atcud = self.env['alert.atcud']
                        sequence_id_atcud = invoice._get_sequence_for_atcud()
                        codigo_validacao_serie = wizard_alert_atcud._get_codigo_validacao_serie(sequence_id_atcud,
                                                                                                invoice.invoice_date)
                        if not codigo_validacao_serie:
                            if self.env.company.series_at_user and self.env.company.series_at_password:
                                # consult if the series has been registered in the AT platform. Register if not.
                                result = self.env['res.config.settings'].register_automatically(
                                    sequences=sequence_id_atcud)
                                self.env['series.wizard.registration.result'].search(
                                    [('id', '=', result['res_id'])]).evaluate_summary()
                                new_code = wizard_alert_atcud._get_codigo_validacao_serie(sequence_id_atcud,
                                                                                          invoice.invoice_date)
                                invoice.message_post(
                                    body=_('Foi atribuído o código de validação de sequência AT: %s' % new_code))
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
                # FIM ATCUD#

    def auto_payment(self):
        for invoice in self:
            if invoice.journal_id.paga_me:
                if not invoice.modo_pagar_vd:
                    raise UserError('Please Select Payment Journal')
                payment_type = "inbound"
                partner_type = 'customer'
                aml = 'credit'
                if invoice.move_type == 'in_invoice':
                    payment_type = "outbound"
                    partner_type = 'supplier'
                    aml = 'debit'
                if invoice.amount_residual > 0:
                    payment_vals = {
                        'payment_type': payment_type,
                        'partner_type': partner_type,
                        'amount': abs(invoice.amount_residual),
                        'date': invoice.invoice_date,
                        'journal_id': invoice.modo_pagar_vd.id,
                        'payment_method_line_id': invoice.payment_method_vd_id.id,
                        'partner_id': invoice.commercial_partner_id.id,
                        'currency_id': invoice.currency_id.id,
                        'reconciled_invoice_ids': [(6, 0, [invoice.id])],
                    }
                    payment = self.env['account.payment'].create(payment_vals)
                    payment.action_post()

                    credit_aml = payment.line_ids.filtered(aml)
                    try:
                        invoice.js_assign_outstanding_line(credit_aml.id)
                    except:
                        e = 1

    def certify(self):
        for invoice in self:
            invoice.treat_atcud()
            invoice.verificar_cliente_data()
            invoice.validar_sequencia_moeda()
            invoice.verificar_linhas_fatura(TYPE2JOURNAL[invoice.move_type])
            invoice.verificar_diarios()
            invoice.verificar_dados_fatura()
            invoice.create_hash()
            invoice.auto_payment()
            invoice.internal_number = invoice.name

    def certify_missing_hash(self):
        for invoice in self:
            invoice.create_hash()
            invoice.internal_number = invoice.name

    def action_post(self):
        super(AccountMove, self).action_post()
        for invoice in self:
            # Verificar se o tipo de diário é 'Fatura Simplificada' e se o total da fatura é igual ou superior a 1000
            if invoice.journal_id.saft_inv_type == 'FS' and invoice.amount_total >= 1000:
                raise UserError(_('O total da fatura não pode ser igual ou superior a 1000, sendo o díário '
                                  'selecionado do tipo "Fatura Simplificada".'))
            # Verificar se o total da fatura é negativo
            if invoice.amount_total < 0:
                raise UserError(_('O total da fatura não pode ser negativo.'))
            # Pesquisar se nao existe uma fatura para esse movimento
            if invoice.journal_id.type == 'sale' and (not invoice.journal_id.manual or \
                                                      not invoice.journal_id.manual) and not invoice.invoice_date:
                raise UserError(_('Não pode publicar movimentos de vendas que nao estejam associados a faturas'))
            if invoice.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
                invoice.certify()

    def _post(self, soft=True):
        post = super(AccountMove, self)._post(soft)
        for invoice in self:
            if invoice.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund') and not invoice.hash:
                invoice.certify()
        return post

    # razao de cancelamento obrigatoria ao cancelar fatura ou nc de venda
    def action_cancel(self):
        for invoice in self:
            if not invoice.reason_cancel and invoice.move_type not in ['in_invoice', 'in_refund']:
                raise ValidationError(_('Incompleto\n'
                                        'Introduza a razão do cancelamento no campo "Descrição" na aba "Outras Informações".'))
        return super(AccountMove, self).action_cancel()

    # metodo para selecionar diario automatico em faturas recibo
    @api.model
    def _get_caixa_defeito(self):
        account_journal = self.env['account.journal'].search([
            ('type', 'in', ['cash', 'bank']),
            ('saft_inv_type', '=', 'receipt'),
            ('por_defeito', '=', True),
            ('company_id', '=', self.env.company.id)], limit=1)
        if account_journal:
            return account_journal.id
        else:
            return False

    def _get_sequence_for_atcud(self):
        for invoice in self:
            if invoice.move_type == 'out_invoice':
                return invoice.journal_id.sequence_id
            if invoice.move_type == 'out_refund':
                return invoice.journal_id.refund_sequence_id

    def _compute_atcud(self):
        for invoice in self:
            invoice.atcud = ''
            if not invoice.company_id.pais_certificacao or invoice.company_id.pais_certificacao.code == 'PT':
                needs_atcud = self.env['ir.config_parameter'].sudo().get_param('needs_atcud')
                if invoice.hash and needs_atcud == 'True' and invoice.move_type in ('out_invoice', 'out_refund'):
                    wizard_atcud = self.env['alert.atcud']
                    sequence_id = invoice._get_sequence_for_atcud()
                    codigo_validacao_serie = wizard_atcud._get_codigo_validacao_serie(sequence_id,
                                                                                      invoice.invoice_date or datime.now())
                    if codigo_validacao_serie:
                        if invoice.name:
                            n_sequencial_serie = invoice.name.split('/')[1]
                        else:
                            n_sequencial_serie = invoice.internal_number.split('/')[1]
                        invoice.atcud = _(codigo_validacao_serie) + '-' + n_sequencial_serie

    def _amount_by_group(self):
        for order in self:
            currency = order.currency_id or order.company_id.currency_id
            fmt = partial(formatLang, self.with_context(lang=order.partner_id.lang).env, currency_obj=currency)
            res = {}
            list_groups = []
            for line in order.invoice_line_ids:
                price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
                taxes = line.tax_ids.compute_all(price_reduce, quantity=line.quantity, product=line.product_id,
                                                 partner=order.partner_id)['taxes']
                for tax in line.tax_ids:
                    group = tax.tax_group_id
                    if group not in list_groups:
                        list_groups.append(group)
                    res.setdefault(group, {'amount': 0.0, 'base': 0.0})
                    for t in taxes:
                        if t['id'] == tax.id or t['id'] in tax.children_tax_ids.ids:
                            res[group]['amount'] += t['amount']
                            res[group]['base'] += t['base']
                            res[group]['saft_tax_code'] = tax.saft_tax_code
                            res[group]['saft_tax_type'] = tax.saft_tax_type
                            res[group]['exemption_reason'] = tax.exemption_reason
                            res[group]['tax_amount'] = tax.amount

            res = sorted(res.items(), key=lambda l: l[0].sequence)
            order.amount_by_group = [(
                l[0].name, l[1]['amount'], l[1]['base'],
                fmt(l[1]['amount']), fmt(l[1]['base']),
                len(res), l[1]['saft_tax_code'], l[1]['exemption_reason'], l[1]['saft_tax_type'], l[1]['tax_amount']
            ) for l in res]
            

    def _get_qr_code_generation(self):
        for invoice in self:
            invoice.qr_code_at = ''
            if invoice.hash:
                nif_empresa = invoice.company_id.vat
                nif_cliente = invoice.partner_id.commercial_partner_id and invoice.partner_id.commercial_partner_id.vat or \
                              invoice.partner_id.vat
                pais_cliente = invoice.partner_id.commercial_partner_id and invoice.partner_id.commercial_partner_id.country_id and \
                               invoice.partner_id.commercial_partner_id.country_id.code or (
                                           invoice.partner_id.country_id and \
                                           invoice.partner_id.country_id.code or 'PT')
                tipo_documento = invoice.journal_id.saft_inv_type
                doc_state = 'N'
                if invoice.state == 'cancel':
                    doc_state = 'A'
                doc_date = invoice.invoice_date
                if invoice.name:
                    numero = invoice.name
                else:
                    numero = invoice.internal_number
                atcud = invoice.atcud or '0'
                espaco_fiscal = 'PT'
                for order_line in invoice.invoice_line_ids:
                    for tax_id in order_line.tax_ids:
                        if tax_id.country_region != 'PT':
                            espaco_fiscal = tax_id.country_region

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

                for tax_by_group in invoice.amount_by_group:
                    if tax_by_group[6] == 'RED':
                        valor_base_red = tax_by_group[2]
                        valor_iva_red = tax_by_group[1]
                    if tax_by_group[6] == 'NOR':
                        valor_base_normal = tax_by_group[2]
                        valor_iva_normal = tax_by_group[1]
                    if tax_by_group[6] == 'INT':
                        valor_base_int = tax_by_group[2]
                        valor_iva_int = tax_by_group[1]
                    if tax_by_group[6] == 'ISE':
                        valor_base_isento = tax_by_group[2]
                    if tax_by_group[6] == 'OUT':
                        valor_n_sujeito_iva = tax_by_group[2]

                total_impostos = invoice.amount_tax
                total_com_impostos = invoice.amount_total

                quatro_caratecters_hash = _(invoice.hash[0:1]) + _(invoice.hash[10:11]) + _(invoice.hash[20:21]) + \
                                          _(invoice.hash[30:31])
                n_certificado = '1456'
                outras_infos = ''

                invoice.qr_code_at = qr_code_generation.qr_code_at(nif_empresa, nif_cliente, pais_cliente,
                                                                   tipo_documento,
                                                                   doc_state, doc_date, numero, atcud,
                                                                   espaco_fiscal, round(valor_base_isento, 2),
                                                                   round(valor_base_red, 2),
                                                                   round(valor_iva_red, 2), round(valor_base_int, 2),
                                                                   round(valor_iva_int, 2),
                                                                   round(valor_base_normal, 2),
                                                                   round(valor_iva_normal, 2),
                                                                   round(valor_n_sujeito_iva, 2)
                                                                   , round(imposto_selo, 2), round(total_impostos, 2),
                                                                   round(total_com_impostos, 2),
                                                                   round(retencao_na_fonte, 2), quatro_caratecters_hash,
                                                                   n_certificado, outras_infos)

    def _compute_qr_code_image(self):
        for invoice in self:
            invoice.qr_code_at_img = self.env['alert.atcud']._compute_qr_code_image(invoice.qr_code_at)

    sequence_generated = fields.Boolean(string="Sequence Generated", copy=False)
    reason_cancel = fields.Char(string="Motivo de Anulação", size=64, readonly=True, copy=False)
    ref_pagamento = fields.Char(string="Referência do Pagamento", size=64, readonly=True, copy=False, default='-')
    hash = fields.Char(string="Hash", size=256, readonly=True, help="Unique hash of the invoice.", copy=False)
    hash_date = fields.Datetime(string="Data em que o hash foi gerado", copy=False)
    cambio = fields.Float(digits=(2, 6), help="Cambio da moeda", default=1)
    product_id = fields.Many2one(string="Produto", related='invoice_line_ids.product_id')
    internal_number = fields.Char(string="Invoice Number", copy=False)
    currency_tax_info = fields.Text(compute='_get_currency_tax_info', readonly=True, string="Câmbio",
                                    help="Valor e data da taxa de cambio definida para a date e moeda da fatura")
    moeda_show = fields.Boolean(compute=_get_moeda_show, readonly=True, default=False)
    hash_control = fields.Char(string="Chave", size=40, copy=False)
    system_entry_date = fields.Datetime(string="Data de confirmação", copy=False)
    write_date = fields.Datetime(string="Data de alteração", copy=False)
    modo_pagar_vd = fields.Many2one('account.journal', string="Método de Pagamento",
                                    default=_get_caixa_defeito, copy=False)
    payment_method_vd_id = fields.Many2one('account.payment.method', string="Modo de Pagamento", copy=False)
    payment_method_vd_id_domain = fields.Char(string="Domain payment_method_vd_id", copy=False,
                                              compute='_onchange_modo_pagar_vd', store=False)
    ref_saft_inv_type = fields.Selection(related='journal_id.saft_inv_type', string="Tipo de Documento",
                                         store=False, readonly=True)
    atcud = fields.Char(compute='_compute_atcud', string='ATCUD')
    qr_code_at = fields.Char(compute='_get_qr_code_generation', string='QR Code AT')
    qr_code_at_img = fields.Binary("QR Code", compute='_compute_qr_code_image')
    amount_by_group = fields.Binary(string="Tax amount by group",
                                    compute='_amount_by_group',
                                    help='Edit Tax amounts if you encounter rounding issues.')
    origin_document_status = fields.Selection([
        ('N', 'Normal'),
        ('A', 'Anulado'),
        ('I', 'Integrado'),
        ('S', 'SourceBilling')],
        string="Estado Documento Original", copy=False)
    journal_id_is_integrado = fields.Boolean(default=False)
    apresentou_decl_recapitulativa = fields.Boolean(string="Apresentou Declaração Recapitulativa", default=False)
    prazo = fields.Char(string="Prazo", default='2')

    @api.depends('modo_pagar_vd')
    def _onchange_modo_pagar_vd(self):
        for invoice in self:
            invoice.payment_method_vd_id_domain = [('id', 'in', [])]
            if invoice.modo_pagar_vd:
                invoice.payment_method_vd_id = (invoice.modo_pagar_vd.inbound_payment_method_line_ids and
                                                invoice.modo_pagar_vd.inbound_payment_method_line_ids[0] and
                                                invoice.modo_pagar_vd.inbound_payment_method_line_ids[
                                                    0].payment_method_id.id
                                                or False)
                list_ids = []
                for line in invoice.modo_pagar_vd.inbound_payment_method_line_ids:
                    list_ids.append(line.payment_method_id.id)
                invoice.payment_method_vd_id_domain = [('id', 'in', list_ids)]

    @api.onchange('journal_id')
    def _onchange_show_integrado(self):
        for move in self:
            if move.journal_id and move.journal_id.integrado:
                move.journal_id_is_integrado = True
            else:
                move.journal_id_is_integrado = False

    # verificar se estes campos n se perdem - bug encontrado mas n replicado no cliente
    @api.constrains('state', 'internal_number', 'hash', 'invoice_date')
    def check_hash_fields_opc(self):
        for invoice in self:
            if invoice.move_type in ('out_invoice', 'out_refund'):
                if invoice.state == 'cancel' and invoice.name:
                    if not invoice.hash or not invoice.invoice_date or not invoice.internal_number:
                        raise ValidationError(_('Faltam dados de faturação, como data, número ou hash.'))
        return True

    @api.depends('posted_before', 'state', 'journal_id', 'date')
    def _compute_name(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                sequence_id = move._get_sequence()
                if not sequence_id:
                    raise UserError(_('Por favor defina uma sequência no diário'))
            if not move.journal_id.sequence_id:
                return super(AccountMove, self)._compute_name()
            sequence_id = move._get_sequence()
            if not sequence_id:
                raise UserError(_('Por favor defina uma sequência no diário'))
            if not move.sequence_generated and move.state == 'draft':
                move.name = '/'
            elif not move.sequence_generated and move.state not in ['draft', False]:
                seq_date = move.invoice_date if move.move_type in \
                                                ('out_invoice', 'out_refund', 'in_invoice', 'in_refund') else move.date
                move.name = sequence_id.next_by_id(seq_date)
                move.sequence_generated = True

    def _get_sequence(self):
        ''' Return the sequence to be used during the post of the current move.
        :return: An ir.sequence record or False.
        '''
        self.ensure_one()

        journal = self.journal_id
        if self.move_type in ('entry', 'out_invoice', 'in_invoice', 'out_receipt', 'in_receipt') \
                or not journal.refund_sequence:
            if journal.type in ('bank', 'cash'):
                if self.payment_id:
                    if self.payment_id.payment_type == 'inbound':
                        return journal.sequence_id
                    else:
                        return journal.refund_sequence_id
                else:
                    return journal.refund_sequence_id
            return journal.sequence_id
        if not journal.refund_sequence_id:
            return
        return journal.refund_sequence_id

    # verificar se o cambio é maior que o 0
    @api.constrains('cambio')
    def check_cambio(self):
        for invoice in self:
            if invoice.cambio <= 0:
                raise ValidationError(_('O Câmbio tem que ser maior que zero'))
        return True

    # verifica se a fatura e do mes corrente e se tem notas de credito associadas
    def write(self, vals):
        for invoice in self:
            if 'state' in vals and vals['state'] == 'cancel':
                if invoice.invoice_date:
                    if (invoice.invoice_date.year < datetime.now().year) or (
                            invoice.invoice_date.year == datetime.now().year and
                            invoice.invoice_date.month < datetime.now().month):
                        if not invoice.journal_id.integrado and invoice.move_type in ['out_invoice', 'out_refund']:
                            if not invoice.company_id.pais_certificacao or (invoice.company_id.pais_certificacao and
                                                                            'Portugal' in invoice.company_id.pais_certificacao.name):
                                raise ValidationError('Aviso\nApenas é possivel cancelar faturas do mês corrente.')
                    if invoice.internal_number:
                        expressao_regular = '(.,|^)(' + invoice.internal_number.replace(' ', '') + ')(,.|$)'
                        self.env.cr.execute("""
                            SELECT ai.internal_number
                            FROM account_move as ai
                            WHERE replace(ai.invoice_origin, ' ', '') ~ concat(%s)
                                and ai.state != 'cancel'
                        """, (expressao_regular,))
                        nota_credito = self.env.cr.fetchall()
                        if len(nota_credito) > 0:
                            raise ValidationError(_('Aviso\n A Fatura possui uma Nota de Crédito associada.'))

            if 'state' in vals:
                if invoice.state != 'draft' and vals['state'] == 'draft' and invoice.move_type in ['out_invoice',
                                                                                                   'out_refund']:
                    raise ValidationError(_("Não pode alterar a fatura para rascunho."))
        return super(AccountMove, self).write(vals)

    def button_cancel(self):
        self.write({'auto_post': 'no', 'state': 'cancel'})

    def unlink(self):
        # so permite anular documentos em rascunho
        for invoice in self:
            if invoice.state == 'draft' or \
                    (invoice.state == 'cancel' and not invoice.internal_number and not invoice.hash):
                if invoice.move_type not in ('out_invoice', 'out_refund'):
                    e = 1
            # integrado cancelado
            elif invoice.state == 'cancel' and invoice.journal_id.integrado is True:
                e = 2
            else:
                raise ValidationError(_('Aviso\n Apenas é possível eliminar documentos no estado de rascunho.'))
        return super().unlink()
