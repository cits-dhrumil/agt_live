# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from datetime import datetime, timedelta
from odoo import models, fields, api, _
from . import creating_hash
from dateutil.relativedelta import relativedelta
from pytz import timezone
from . import qr_code_generation
from functools import partial
from odoo.tools.misc import formatLang
from odoo.exceptions import UserError, RedirectWarning, ValidationError

tz_pt = timezone('Europe/Lisbon')


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    def _get_sequence_for_atcud(self):
        for sale in self:
            sequence_id = False
            if sale.type_doc == 'OR':
                sequence_id = self.env['ir.sequence'].sudo().search([('code', '=', 'sale.order.or'),
                                                                     '|', ('company_id', '=', sale.company_id.id),
                                                                     ('company_id', '=', False)], limit=1)
            elif sale.type_doc == 'PP':
                sequence_id = self.env['ir.sequence'].sudo().search([('code', '=', 'pro.forma'),
                                                                     '|', ('company_id', '=', sale.company_id.id),
                                                                     ('company_id', '=', False)], limit=1)
            elif sale.type_doc == 'FC':
                sequence_id = self.env['ir.sequence'].sudo().search([('code', '=', 'cosignation'),
                                                                     '|', ('company_id', '=', sale.company_id.id),
                                                                     ('company_id', '=', False)], limit=1)
            elif sale.type_doc == 'NE':
                sequence_id = self.env['ir.sequence'].sudo().search([('code', '=', 'nota.encomenda'),
                                                                     '|', ('company_id', '=', sale.company_id.id),
                                                                     ('company_id', '=', False)], limit=1)
            if not sequence_id:
                sequence_id = self.env['ir.sequence'].sudo().search([('code', '=', 'sale.order.or'),
                                                                     '|', ('company_id', '=', sale.company_id.id),
                                                                     ('company_id', '=', False)], limit=1)
            return sequence_id

    def _compute_atcud(self):
        for sale in self:
            sale.atcud = ''
            needs_atcud = self.env['ir.config_parameter'].sudo().get_param('needs_atcud')
            if sale.hash and needs_atcud == 'True':
                wizard_atcud = self.env['alert.atcud']
                sequence_id = sale._get_sequence_for_atcud()
                codigo_validacao_serie = wizard_atcud._get_codigo_validacao_serie(sequence_id, sale.date_order)
                if codigo_validacao_serie:
                    n_sequencial_serie = sale.name.split('/')[1]
                    sale.atcud = _(codigo_validacao_serie) + '-' + n_sequencial_serie

    def _get_qr_code_generation(self):
        for sale in self:
            sale.qr_code_at = ''
            if sale.hash:
                nif_empresa = sale.company_id.vat
                nif_cliente = sale.partner_id.commercial_partner_id and sale.partner_id.commercial_partner_id.vat or \
                              sale.partner_id.vat
                pais_cliente = sale.partner_id.commercial_partner_id and sale.partner_id.commercial_partner_id.country_id and \
                               sale.partner_id.commercial_partner_id.country_id.code or (sale.partner_id.country_id and \
                                                                                         sale.partner_id.country_id.code or 'PT')
                tipo_documento = sale.type_doc
                doc_state = 'N'
                if sale.state == 'cancel':
                    doc_state = 'A'
                doc_date = sale.date_order
                numero = sale.name.split(' ')[1]
                atcud = sale.atcud
                espaco_fiscal = 'PT'
                for order_line in sale.order_line:
                    for tax_id in order_line.tax_id:
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

                for tax_by_group in sale.amount_by_group:
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

                total_impostos = sale.amount_tax
                total_com_impostos = sale.amount_total

                quatro_caratecters_hash = _(sale.hash[0:1]) + _(sale.hash[10:11]) + _(sale.hash[20:21]) + \
                                          _(sale.hash[30:31])
                n_certificado = '1456'
                outras_infos = ''

                sale.qr_code_at = qr_code_generation.qr_code_at(nif_empresa, nif_cliente, pais_cliente, tipo_documento,
                                                                doc_state, doc_date, numero, atcud,
                                                                espaco_fiscal, round(valor_base_isento, 2),
                                                                round(valor_base_red, 2),
                                                                round(valor_iva_red, 2), round(valor_base_int, 2),
                                                                round(valor_iva_int, 2),
                                                                round(valor_base_normal, 2), round(valor_iva_normal, 2),
                                                                round(valor_n_sujeito_iva, 2)
                                                                , round(imposto_selo, 2), round(total_impostos, 2),
                                                                round(total_com_impostos, 2),
                                                                round(retencao_na_fonte, 2), quatro_caratecters_hash,
                                                                n_certificado, outras_infos)

    def _amount_by_group(self):
        for order in self:
            currency = order.currency_id or order.company_id.currency_id
            fmt = partial(formatLang, self.with_context(lang=order.partner_id.lang).env, currency_obj=currency)
            res = {}
            for line in order.order_line:
                price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
                taxes = line.tax_id.compute_all(price_reduce, quantity=line.product_uom_qty, product=line.product_id,
                                                partner=order.partner_shipping_id)['taxes']
                for tax in line.tax_id:
                    group = tax.tax_group_id
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

    
    def _compute_qr_code_image(self):
        for sale in self:
            sale.qr_code_at_img = self.env['alert.atcud']._compute_qr_code_image(sale.qr_code_at)

    hash = fields.Char(string="Hash", size=256, readonly=True, help="Unique hash of the sale order.", copy=False)
    hash_control = fields.Char(string="key", size=40, copy=False)
    hash_date = fields.Datetime(string="Date the hash was generated", copy=False)
    type_doc = fields.Selection([('OR', 'Date the hash was generated'),
                                 ('NE', 'Order Form'),
                                 ('PP', 'Pro-Forma'),
                                 ('FC', 'Consignment')], readonly=True, copy=False)
    certificated = fields.Boolean('Certificated', default=False, copy=False, readonly=True)
    old_name_proforma = fields.Char('Proforma', copy=False, search='_name_search', readonly=True)
    old_name_quotation = fields.Char('Quotation', copy=False, search='_name_search', readonly=True)
    old_name = fields.Char('Quotation draft', copy=False, search='_name_search', readonly=True)
    confirmed = fields.Boolean('Confirmed', copy=False, readonly=True, default=False)
    descricao_cancel = fields.Char(string="Reason for Cancellation", size=64, copy=False)
    atcud = fields.Char(compute='_compute_atcud', string='ATCUD')
    qr_code_at = fields.Char(compute='_get_qr_code_generation', string='QR Code AT')
    qr_code_at_img = fields.Binary("QR Code", compute='_compute_qr_code_image')
    amount_by_group = fields.Binary(string="Tax amount by group", compute='_amount_by_group', help="type: [(name, amount, base, formated amount, formated base)]")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (not self.env.context.get(
                    'default_type_doc') and not self.type_doc) or self.type_doc == 'NE':
                vals.update({
                    'type_doc': 'OR'})
        return super(SaleOrder, self).create(vals_list)

    def write(self, vals):
        super_write = super(SaleOrder, self).write(vals)
        if 'state' in vals and vals['state'] == 'draft':
            for sale_order in self:
                if sale_order.certificated:
                    raise ValidationError(
                        _('You can not change the state of a certified document to draft!'))
        return super_write

    def copy(self, default=None):
        default = {} if default is None else default.copy()
        for sale_order in self:
            if sale_order.type_doc:
                default.update({'type_doc': sale_order.type_doc})
        return super(SaleOrder, self).copy(default)

    def unlink(self):
        for line in self:
            if line.state == 'draft' and not line.certificated:
                return super(SaleOrder, self).unlink()
            else:
                raise ValidationError(
                    _('Aviso\n Apenas é possível eliminar documentos '
                      'no estado de rascunho e não certificados.'))

    def certify(self):
        if not self.company_id.pais_certificacao or self.company_id.pais_certificacao.code == 'PT':
            needs_atcud = self.env['ir.config_parameter'].sudo().get_param('needs_atcud')
            if needs_atcud == 'True':
                wizard_alert_atcud = self.env['alert.atcud']
                sequence_id_atcud = self._get_sequence_for_atcud()
                codigo_validacao_serie = wizard_alert_atcud._get_codigo_validacao_serie(sequence_id_atcud, self.date_order)
                if not codigo_validacao_serie:
                    if self.env.company.series_at_user and self.env.company.series_at_password:
                        # consult if the series has been registered in the AT platform. Register if not.
                        result = self.env['res.config.settings'].register_automatically(sequences=sequence_id_atcud)
                        self.env['series.wizard.registration.result'].search([('id', '=', result['res_id'])]).evaluate_summary()
                        new_code = wizard_alert_atcud._get_codigo_validacao_serie(sequence_id_atcud, self.date_order)
                        self.message_post(body=_('Foi atribuído o código de validação de sequência AT: %s' % new_code))
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

        if not self.certificated:
            self.env.cr.execute("""
                           SELECT max(date_order)
                           FROM sale_order
                           WHERE hash != ''""")
            max_date = self.env.cr.fetchone()[0]
            if max_date and self.date_order < max_date:
                self.date_order = max_date + timedelta(minutes=1)
        if self.state == 'draft':
            data = datetime(datetime.now().year, datetime.now().month, 1)
            if str(self.date_order) >= (datetime(datetime.now(tz_pt).year, datetime.now(tz_pt).month, 1) +
                                        relativedelta(months=1)).strftime('%Y-%m-%d'):
                raise ValidationError('Aviso\n Apenas é possivel certificar orçamentos com data superior ao dia'
                                      ' 1 do mês corrente.')
        if not self.order_line:
            raise ValidationError(_('You cannot certify a document with no product. Insert a product.'))
        else:
            line_no = 0
            for line in self.order_line:
                if line.product_id:
                    line_no += 1
                if not line.tax_id:
                    if line.product_id:
                        raise ValidationError('Todas as linhas tem de ter imposto.')
            if line_no == 0:
                raise ValidationError(_('There must be at least a product in order lines'
                                        ' in order to certify the document.'))
            if self.type_doc == 'OR' and not self.certificated:
                self.old_name = self.name
                ctx = dict(self.env.context, with_company=self.company_id.id)
                self.name = self.env['ir.sequence'].with_context(ctx).next_by_code('sale.order.or', self.date_order)
            elif self.type_doc == 'PP' and not self.certificated:
                self.old_name_proforma = self.name
                self.name = self.env['ir.sequence'].next_by_code('pro.forma', self.date_order)
            elif self.type_doc == 'FC' and not self.certificated:
                self.old_name = self.name
                self.name = self.env['ir.sequence'].next_by_code('cosignation', self.date_order)

            for sale_order in self:
                datasistema = str(sale_order.write_date or datetime.now())[:19]
                datadocumento = sale_order.date_order
                number = sale_order.name
                totalbruto = sale_order.amount_total
                self._cr.execute("select count(*) from sale_order where hash != '' and company_id=" +
                                 str(sale_order.company_id.id))
                numHash = self._cr.fetchone()[0]
                antigoHash = False
                if numHash > 0:
                    self._cr.execute("SELECT so.hash FROM sale_order so, (select max(id) from sale_order " +
                                     "where hash != '' and company_id=" + str(sale_order.company_id.id) +
                                     ") mso where so.id = mso.max")
                    antigoHash = self._cr.fetchone()[0]

                values = creating_hash.hash(
                    self, False, datadocumento, datasistema, number, numHash, antigoHash, totalbruto)
                self.certificated = True
                sale_order.write(values)

    def action_quotation_send(self):
        if not self.certificated:
            self.certify()
        return super(SaleOrder, self).action_quotation_send()

    def action_confirm(self):
        for sale in self:
            if sale.amount_total < 0:
                raise UserError(_('Aviso!\nNão é possível confirmar uma venda com valor negativo.'))
            sale.confirmed = True
            if sale.type_doc == 'OR':
                sale.old_name_quotation = self.name
                sale.name = self.env['ir.sequence'].next_by_code('nota.encomenda', sale.date_order)
                sale.type_doc = 'NE'
            sale.certify()
        return super(SaleOrder, self).action_confirm()

    
    def action_cancel(self):
        if not self.descricao_cancel:
            raise ValidationError(_('Incompleto.\n'
                                    'Introduza a razão do cancelamento no campo "Motivo do Cancelamento".'))
        return super(SaleOrder, self).action_cancel()

    def grosstotal(self):
        integer, decimal = str(self.amount_total).split('.')
        return '.'.join([integer, decimal.ljust(2, '0')])

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.constrains('discount')
    def _check_value(self):
        for sale_line in self:
            discount = sale_line.discount
            if discount < 0 or discount > 100:
                raise ValidationError('O valor do desconto deve estar entre 0% e 100%.')
            return True

    @api.constrains('tax_id')
    def _constraint_tax_id_one_tax(self):
        for sale_line in self:
            if len(sale_line.tax_id) >= 2:
                raise ValidationError(_('Está a utilizar mais do que um imposto!'))
            return True
