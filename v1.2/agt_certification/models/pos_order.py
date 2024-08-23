# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from datetime import datetime
from odoo import models, fields, _ ,api
from . import creating_hash
from pytz import timezone
from . import qr_code_generation
tz_pt = timezone('Europe/Lisbon')


class POSOrder(models.Model):
    """Inherit pos.order Model."""
    _inherit = 'pos.order'

    def _prepare_invoice_vals(self):
        """Override this method to Pass Static string "POS REFUND"
        in reason_cancel."""
        vals = super()._prepare_invoice_vals()
        vals.update({'reason_cancel': 'POS REFUND'})
        return vals

    hash = fields.Char(string="Hash", size=256, readonly=True,
                       help="Unique hash of the sale order.", copy=False)
    hash_control = fields.Char(string="Chave", size=40, copy=False)
    hash_date = fields.Datetime(string="Data em que o hash foi gerado",
                                copy=False)
    certificated = fields.Boolean('Certificated', default=False, copy=False,
                                  readonly=True)
    atcud = fields.Char(compute='_compute_atcud', string='ATCUD')
    qr_code_at = fields.Char(compute='_get_qr_code_generation',
                             string='QR Code AT')
    qr_code_at_img = fields.Binary("QR Code", compute='_compute_qr_code_image')
    old_name = fields.Char(string="Referência interna", size=64, copy=False)

    def certify(self):
        '''certify the quotation and then after not editable '''
        needs_atcud = self.env['ir.config_parameter'].sudo().get_param('needs_atcud')
        if needs_atcud == 'True':
            # Todo: needs_atcud field is not defined in configuration part so
            #  this condition always going false
            wizard_alert_atcud = self.env['alert.atcud']
            sequence_id_atcud = self._get_sequence_for_atcud()
            codigo_validacao_serie = wizard_alert_atcud._get_codigo_validacao_serie(sequence_id_atcud, self.date_order)
        if not self.certificated:
            self.env.cr.execute("""
                SELECT max(date_order)
                FROM pos_order
                WHERE hash != ''""")
            self.env.cr.fetchone()[0]
        for pos_order in self:
            datasistema = str(pos_order.write_date or datetime.now())[:19]
            datadocumento = pos_order.date_order
            number = pos_order.name
            totalbruto = pos_order.amount_total
            # verificar se é o primeiro documento
            self._cr.execute("select count(*) from pos_order where hash != '' and company_id=" +
                             str(pos_order.company_id.id))
            numHash = self._cr.fetchone()[0]
            # Se não for o primeiro vai buscar o hash anterior
            antigoHash = False
            if numHash > 0:
                self._cr.execute("SELECT pos.hash FROM pos_order pos, (select max(id) from pos_order " +
                                 "where hash != '' and company_id=" + str(pos_order.company_id.id) +
                                 ") mso where pos.id = mso.max")
                antigoHash = self._cr.fetchone()[0]
            values = creating_hash.hash(
                self, False, datadocumento,
                datasistema, number, numHash, antigoHash, totalbruto)
            self.certificated = True
            pos_order.write(values)


    def _get_sequence_for_atcud(self):
        '''get sequence '''
        #Todo This is not calling now because of configurations for
        # actud is not there
        for pos in self:
            sequence_id = self.env['ir.sequence'].sudo().search(
                [('code', '=', 'pos.order.custom'),
                 '|', ('company_id', '=', pos.company_id.id),
                 ('company_id', '=', False)], limit=1)
            return sequence_id

    def _compute_atcud(self):
        '''Compute or find sequence for order based date range or default
        configurations'''
        for pos in self:
            pos.atcud = ''
            #Todo needs_atcud need to add in configurations
            # part and then we can actual set that variable values
            needs_atcud = self.env['ir.config_parameter'].sudo().get_param(
                'needs_atcud')
            if pos.hash and needs_atcud == 'True':
                wizard_atcud = self.env['alert.atcud']
                sequence_id = pos._get_sequence_for_atcud()
                codigo_validacao_serie = wizard_atcud._get_codigo_validacao_serie(
                    sequence_id, pos.date_order)
                if codigo_validacao_serie:
                    n_sequencial_serie = pos.name.split('/')[1]
                    pos.atcud = _(
                        codigo_validacao_serie) + '-' + n_sequencial_serie

    def _get_qr_code_generation(self):
        '''Generate qr code'''
        #Todo we are making same as sale order references
        for pos in self:
            pos.qr_code_at = ''
            if pos.hash:
                nif_empresa = pos.company_id.vat
                nif_cliente = pos.partner_id.commercial_partner_id and pos.partner_id.commercial_partner_id.vat or \
                              pos.partner_id.vat
                pais_cliente = pos.partner_id.commercial_partner_id and pos.partner_id.commercial_partner_id.country_id and \
                               pos.partner_id.commercial_partner_id.country_id.code or (
                                       pos.partner_id.country_id and \
                                       pos.partner_id.country_id.code or 'PT')
                tipo_documento = 'Test'
                doc_state = 'N'
                if pos.state == 'cancel':
                    doc_state = 'A'
                doc_date = pos.date_order
                numero = pos.name.split(' ')[1]
                atcud = pos.atcud
                espaco_fiscal = 'PT'
                for order_line in pos.lines:
                    for tax_id in order_line.tax_ids_after_fiscal_position:
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

                for tax_by_group in pos.amount_by_group:
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

                total_impostos = pos.amount_tax
                total_com_impostos = pos.amount_total

                quatro_caratecters_hash = _(pos.hash[0:1]) + _(
                    pos.hash[10:11]) + _(pos.hash[20:21]) + \
                                          _(pos.hash[30:31])
                n_certificado = '0000'
                outras_infos = ''

                pos.qr_code_at = qr_code_generation.qr_code_at(
                    nif_empresa, nif_cliente, pais_cliente, tipo_documento, doc_state, doc_date, numero, atcud, espaco_fiscal,
                    round(valor_base_isento, 2), round(valor_base_red, 2), round(valor_iva_red, 2), round(valor_base_int, 2), round(valor_iva_int, 2),
                    round(valor_base_normal, 2), round(valor_iva_normal, 2), round(valor_n_sujeito_iva, 2), round(imposto_selo, 2),
                    round(total_impostos, 2), round(total_com_impostos, 2), round(retencao_na_fonte, 2),
                    quatro_caratecters_hash, n_certificado, outras_infos
                )

    def _compute_qr_code_image(self):
        '''get qr code image '''
        for pos in self:
            pos.qr_code_at_img = self.env[
                'alert.atcud']._compute_qr_code_image(pos.qr_code_at)

    def _process_saved_order(self,draft):
        '''overright this method for certified the order'''
        draft = super()._process_saved_order(draft)
        self.certify()
        return draft
