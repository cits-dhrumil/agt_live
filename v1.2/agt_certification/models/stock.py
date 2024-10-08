# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

import datetime
import sys
from datetime import datetime, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from . import creating_hash
from pytz import timezone
from . import qr_code_generation

tz_pt = timezone('Europe/Lisbon')


class StockMove(models.Model):
    _inherit = "stock.move"


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    call_at = fields.Boolean(string="automatic AT",
                             help="Check (checkmark) if it is a default to communicate the delivery notes to AT "
                                  "when these are validated.",
                             default=True, copy=False)
    sequence_id_validate = fields.Many2one('ir.sequence', string='Validated Sequence')
    sequence_id_gd_validate = fields.Many2one('ir.sequence', string='Validated GD Sequence')

    def write(self, vals):
        for picking_type in self:
            if 'sequence_id_validate' in vals:
                stock_picking_ids = self.env['stock.picking'].search(
                    [('state', 'in', ('done', 'cancel')),
                     ('picking_type_id', '=', picking_type.id)])
                if len(stock_picking_ids) > 0:
                    raise ValidationError(
                        _('Já existem guias a usar essa sequencia, não pode alterar!'))

            if 'sequence_id_gd_validate' in vals:
                stock_picking_return_ids = self.env['stock.picking'].search(
                    [('state', 'in', ('done', 'cancel')),
                     ('picking_type_id', '=', picking_type.id),
                     ('is_gd', '=', True)])
                if len(stock_picking_return_ids) > 0:
                    raise ValidationError(
                        _('Já existem guias de devolução a usar essa sequencia, não pode alterar!'))
        return super(StockPickingType, self).write(vals)

    @api.constrains('sequence_id_validate', 'sequence_id_gd_validate')
    def _check_sequence_(self):
        if self.sequence_id_validate and self.sequence_id_gd_validate and \
                        self.sequence_id_validate == self.sequence_id_gd_validate:
            raise ValidationError("As sequências de guias validadas e de guias de devolução tem de ser diferentes!")
        return True

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _compute_atcud(self):
        for picking in self:
            picking.atcud = ''
            needs_atcud = self.env['ir.config_parameter'].sudo().get_param('needs_atcud')
            if picking.hash and needs_atcud == 'True':
                wizard_atcud = self.env['alert.atcud']
                sequence_id = picking._get_sequence_for_atcud()
                codigo_validacao_serie = wizard_atcud._get_codigo_validacao_serie(sequence_id, picking.date)
                if codigo_validacao_serie:
                    n_sequencial_serie = picking.name.split('/')[1]
                    picking.atcud = _(codigo_validacao_serie) + '-' + n_sequencial_serie
    
    def _get_sequence_for_atcud(self):
        for picking in self:
            ir_sequence = self.env['ir.sequence']
            if picking.is_gd:
                if picking.picking_type_id.sequence_id_gd_validate:
                    return picking.picking_type_id.sequence_id_gd_validate
                else:
                    return ir_sequence.sudo().search([('code', '=', 'stock.picking.gd.validate'),
                                                      ('company_id', 'in', (picking.company_id.id, False))], limit=1)
            else:
                if picking.picking_type_id.sequence_id_validate:
                    return picking.picking_type_id.sequence_id_validate
                else:
                    if picking.picking_type_id.code == 'incoming':
                        return ir_sequence.sudo().search([('code', '=', 'stock.picking.in.validate'),
                                                          ('company_id', 'in', (picking.company_id.id, False))], limit=1)
                    if picking.picking_type_id.code == 'outgoing':
                        return ir_sequence.sudo().search([('code', '=', 'stock.picking.out.validate'),
                                                          ('company_id', 'in', (picking.company_id.id, False))],
                                                         limit=1)
                    if picking.picking_type_id.code == 'internal':
                        return ir_sequence.sudo().search([('code', '=', 'stock.picking.internal.validate'),
                                                          ('company_id', 'in', (picking.company_id.id, False))],
                                                         limit=1)

    def _compute_qr_code_image(self):
        for picking in self:
            picking.qr_code_at_img = self.env['alert.atcud']._compute_qr_code_image(picking.qr_code_at)

    def _get_qr_code_generation(self):
        for picking in self:
            picking.qr_code_at = ''
            if picking.hash:
                nif_empresa = picking.company_id.vat
                nif_cliente = picking.partner_id.commercial_partner_id and picking.partner_id.commercial_partner_id.vat or \
                              picking.partner_id.vat
                pais_cliente = picking.partner_id.commercial_partner_id and picking.partner_id.commercial_partner_id.country_id and \
                               picking.partner_id.commercial_partner_id.country_id.code or (picking.partner_id.country_id and \
                                                                                         picking.partner_id.country_id.code or 'PT')

                wizard_atcud = self.env['alert.atcud']
                tipo_documento = wizard_atcud.get_tipo_documento_from_sequence(self._get_sequence_for_atcud())
                doc_state = 'N'
                if picking.state == 'cancel':
                    doc_state = 'A'
                doc_date = picking.date
                numero = picking.name
                atcud = picking.atcud
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

                quatro_caratecters_hash = _(picking.hash[0:1]) + _(picking.hash[10:11]) + _(picking.hash[20:21]) + \
                                          _(picking.hash[30:31])
                n_certificado = '0000'
                outras_infos = ''

                picking.qr_code_at = qr_code_generation.qr_code_at(nif_empresa, nif_cliente, pais_cliente, tipo_documento,
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

    def action_cancel(self):
        for picking in self:
            if picking.state == 'done':
                return True
        return super(StockPicking, self).action_cancel()

    at_code = fields.Char(string="AT Code", size=256, readonly=True, copy=False, default='')
    at_status = fields.Selection([('draft', 'Draft'), ('validated', 'Validated'), ('error', 'Error'),
                                  ('success', 'Success'), ('cancel', 'Cancel')], string="AT State", default="draft",
                                 copy=False)
    at_code_message = fields.Char(string="AT code message", readonly=True, copy=False)
    is_gc = fields.Boolean(string="Consignment Guide", default=False, copy=False)
    is_gd = fields.Boolean(string="Return Guide", default=False, copy=False)
    call_at = fields.Boolean(string="automatic AT",
                             help="Check (checkmark) if it is to inform AT of the guide when it is validated.",
                             copy=False, default=False)
    manual = fields.Boolean(string="Manual Guide",
                            help="Put a tick if the Guide was previously created by hand.", copy=False)
    veiculo = fields.Char(string="Registration", size=64, copy=False)
    data_carga = fields.Datetime(string="Load Date", copy=False)
    data_descarga = fields.Datetime(string="Discharge Date", copy=False)
    carga_rua = fields.Char(string="Road", size=256, copy=False)
    carga_cp = fields.Char(string="zip code", size=256, copy=False)
    carga_cidade = fields.Char(string="City", size=256, copy=False)
    carga_pais = fields.Many2one('res.country', string="Country", copy=False)
    descarga_rua = fields.Char(string="Road", size=256, copy=False)
    descarga_cp = fields.Char(string="zip code", size=256, copy=False)
    descarga_cidade = fields.Char(string="City", size=256, copy=False)
    descarga_pais = fields.Many2one('res.country', string="Country", copy=False)
    stop_update = fields.Boolean(string="Fix Addresses",
                                 help="Mark if the addresses were edited manually and not"
                                      "automatically change when changing clients or locations.",
                                 copy=False)
    usar_dados_client = fields.Boolean(string="Use customer data",
                                       help="Put a tick if you want to use customer data in "
                                            "discharge.",
                                       default=True, copy=False)
    usar_dados_empresa = fields.Boolean(string="Use company data",
                                        help="Put a check mark if you intend to use company data in business data."
                                             "discharge.",
                                        default=True, copy=False)
    old_name = fields.Char(string="Internal reference", size=64, copy=False)
    hash = fields.Char(string="Hash", size=256, readonly=True, help="Unique hash of the deliver order.", copy=False)
    hash_control = fields.Char(string="key", size=40, copy=False)
    hash_date = fields.Datetime(string="Date the hash was generated", copy=False)
    atcud = fields.Char(compute='_compute_atcud', string='ATCUD')
    qr_code_at = fields.Char(compute='_get_qr_code_generation', string='QR Code AT')
    qr_code_at_img = fields.Binary("QR Code", compute='_compute_qr_code_image')

    def do_new_transfer(self):
        for pick in self:
            if pick.picking_type_id.code != 'incoming':
                for picking in self.env['stock.picking'].search([('state', '=', 'done'), ('date', '>', pick.date)]):
                    if picking.picking_type_id.id == pick.picking_type_id.id:
                        raise UserError(_('Não pode haver uma guia com data inferior a uma guia validada!'))
        return super(StockPicking, self).do_new_transfer()

    def validar_hash(self):
        self.env.cr.execute("""
            SELECT COUNT(*)
            FROM stock_picking s
            WHERE s.hash != ''  and
            s.picking_type_id=%s and
            extract(YEAR FROM s.date)=%s and
            s.company_id=%s""", (self.picking_type_id.id, self.date.year, self.company_id.id))
        numHash = self.env.cr.fetchone()[0]
        antigoHash = False
        if numHash > 0:
            self.env.cr.execute("""
                            SELECT sp.hash
                            FROM stock_picking sp, (
                                select max(name)
                                from stock_picking
                                where hash!='' and  picking_type_id=%s and id!=%s) msp
                            WHERE sp.picking_type_id=%s and sp.name = msp.max""",
                                (self.picking_type_id.id, self.id, self.picking_type_id.id))
            antigoHash = self.env.cr.fetchone()[0]

        return numHash, antigoHash

    def button_validate(self):
        for picking in self:
            if picking.picking_type_id.code != 'incoming' or picking.is_gd:
                if not picking.company_id.pais_certificacao or picking.company_id.pais_certificacao.code == 'PT':
                    needs_atcud = self.env['ir.config_parameter'].sudo().get_param('needs_atcud')
                    if needs_atcud == 'True':
                        wizard_alert_atcud = self.env['alert.atcud']
                        sequence_id_atcud = picking._get_sequence_for_atcud()
                        codigo_validacao_serie = wizard_alert_atcud._get_codigo_validacao_serie(sequence_id_atcud, picking.date)
                        if not codigo_validacao_serie:
                            if self.env.company.series_at_user and self.env.company.series_at_password:
                                # consult if the series has been registered in the AT platform. Register if not.
                                result = self.env['res.config.settings'].register_automatically(sequences=sequence_id_atcud)
                                self.env['series.wizard.registration.result'].search([('id', '=', result['res_id'])]).evaluate_summary()
                                new_code = wizard_alert_atcud._get_codigo_validacao_serie(sequence_id_atcud,
                                                                                          picking.date)
                                picking.message_post(body=_('Foi atribuído o código de validação de sequência AT: %s' % new_code))

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
        res = super(StockPicking, self).button_validate()
        for pick in self:
            if pick.move_ids_without_package:
                for line in pick.move_ids_without_package:
                    if line.product_uom_qty == 0.0:
                        raise UserError(_('Para validar a guia, o campo "Procura Inicial" tem de ser superior a 0.'))
            if len(pick.move_ids) > 0:
                tipo = 'internal'
                if pick.picking_type_id and pick.picking_type_id.code == 'outgoing':
                    tipo = 'out'
                if pick.picking_type_id and pick.picking_type_id.code == 'incoming':
                    tipo = 'in'

                if pick.is_gd:  # é GD
                    if pick.picking_type_id.sequence_id_gd_validate and pick.picking_type_id.sequence_id_gd_validate.id:
                            sequencia = pick.picking_type_id.sequence_id_gd_validate
                            if sequencia.implementation != 'no_gap':
                                raise ValidationError(_('Deve definir a sequência como "Sem Espaços".'))
                    else:
                        sequencia = self.env['ir.sequence'].search([('code', '=', 'stock.picking.gd.validate'),
                                                                    ('company_id', '=', pick.company_id.id)])
                        if sequencia.implementation != 'no_gap':
                            raise ValidationError(_('Deve definir a sequência como "Sem Espaços".'))
                else:
                    if pick.picking_type_id.sequence_id_validate and pick.picking_type_id.sequence_id_validate.id:
                        sequencia = pick.picking_type_id.sequence_id_validate
                        if sequencia.implementation != 'no_gap':
                            raise ValidationError(_('Deve definir a sequência como "Sem Espaços".'))
                    else:
                        sequencia = self.env['ir.sequence'].search([
                            ('code', '=', 'stock.picking.' + tipo + ".validate"),
                            ('company_id', '=', pick.company_id.id)], limit=1)
                        if sequencia.implementation != 'no_gap':
                            raise ValidationError(_('Deve definir a sequência como "Sem Espaços".'))

                if not pick.hash:
                    if pick.scheduled_date:
                        anofiscal = pick.scheduled_date.year

                    ano_actual = datetime.now().year
                    if anofiscal < ano_actual:
                        raise ValidationError('Nao pode validar para anos anteriores ao corrente.')

                    pick.old_name = str(pick.name)
                    pick.name = sequencia.next_by_id(pick.date_done)

                    #hash

                    datadocumento = str(pick.date)
                    datasistema = str(pick.write_date)[:19]

                    numHash, antigoHash = pick.validar_hash()

                    values = creating_hash.hash(self, False, datadocumento, datasistema, pick.name, numHash,
                                                  antigoHash, 0)
                    pick.write(values)


            if pick.at_status != 'success':
                if pick.call_at:
                    pick.call()
                else:
                    pick.at_status = 'validated'
        return res

    def callWebServiceGRMethod(self):
        for stock_picking in self:
            stock_picking.callWebServiceGR(False)

    def callWebServiceGR(self, cancelar=False):
        def _validar_endereco(entidade, vat, name, street, city, zip, country):
            if not vat:
                raise ValidationError(_('%s não possui NIF!' % entidade))
            if not name:
                raise ValidationError(_('%s não possui Nome!' % entidade))
            if not street:
                raise ValidationError(_('%s não possui Rua!' % entidade))
            if not city:
                raise ValidationError(_('%s não possui Cidade!' % entidade))
            if not zip:
                raise ValidationError(_('%s não possui Código Postal!' % entidade))
            if zip and len(zip) != 8:
                raise ValidationError(_('%s não possui um Código Postal válido!' % entidade))
            if not country:
                raise ValidationError(_('%s não possui País!' % entidade))

        for picking in self:
            ambas_localizacoes_internas = False
            url_param = self.env['ir.config_parameter'].search([('key', '=', 'web.base.url'),
                                                                ('value', 'ilike', '%teste%')])
            if len(url_param) > 0:
                return True

            picking_type_id = picking.picking_type_id.code
            if picking_type_id == "incoming" and picking.is_gd is False:
                return True

            self.env.cr.execute("""SELECT count(sm.id)
                       FROM stock_move sm, stock_location sl
                       WHERE sl.usage!='internal' and
                       sl.id=sm.location_dest_id and
                       sm.picking_id=%s""", (picking.id, ))
            count_stock_move = self.env.cr.fetchone()[0]
            if picking_type_id != 'incoming' and int(count_stock_move) == 0:
                ambas_localizacoes_internas = True

            if picking.usar_dados_client is False:
                _validar_endereco('O cliente', '999999999', 'Consumidor Final', picking.descarga_rua,
                                  picking.descarga_cidade, picking.descarga_cp, picking.descarga_pais)
            utilizador_financas = self.env['utilizador.financas'].search([('name', '=', 'WDT'),
                                                    ('company_id', '=', self.env.user.company_id.id)])

            if utilizador_financas:
                util_id = utilizador_financas.user
                util_pass = utilizador_financas.passe
                por_defeito = utilizador_financas.por_defeito
                por_defeito_matricula = utilizador_financas.por_defeito_matricula
                por_defeito_minutos = utilizador_financas.por_defeito_minutos or 0

            else:
                raise ValidationError(_('Falta definir o utilizador das finanças com permissões WDT!'))

            emp = self.env.user.company_id.partner_id
            if emp:
                _validar_endereco('A sua empresa', emp.vat, emp.name, emp.street, emp.city, emp.zip,
                                       emp.country_id)
                nif_remetente = emp.vat or '999999999'
                nome_empresa = emp.name or ''
                empresa_rua = emp.street or ''
                empresa_cidade = emp.city or ''
                empresa_codigo_postal = emp.zip or ''
                empresa_pais = emp.country_id.code

                if picking.usar_dados_empresa is False:
                    if not picking.carga_rua and not picking.carga_cp and not picking.carga_cidade and \
                            not picking.carga_pais:
                        raise ValidationError(_('Falta definir os dados de carga na aba Inf. Adicional!'))
                    else:
                        carga_rua = picking.carga_rua or ''
                        carga_codigo_postal = picking.carga_cp or ''
                        carga_cidade = picking.carga_cidade or ''
                        carga_pais = picking.carga_pais.code
                else:
                    carga_rua = empresa_rua
                    carga_codigo_postal = empresa_codigo_postal
                    carga_cidade = empresa_cidade
                    carga_pais = empresa_pais
            else:
                raise ValidationError(_('Falta definir dados da empresa!'))

            if picking.at_status != 'success' or cancelar:
                if not picking.name:
                    raise ValidationError(_('A guia não possui número!'))
                doc_number = picking.name
                doc_estado = 'N'
                docATCODE = ''
                if cancelar is True:
                    doc_estado = 'A'
                    docATCODE = picking.at_code or ''
                doc_data = str(picking.date)[:10]
                doc_tipo = 'GR'
                if picking.is_gc is True:
                    doc_tipo = 'GC'
                elif picking_type_id == 'internal':
                    doc_tipo = 'GT'
                if picking.is_gd is True:
                    doc_tipo = 'GD'
                cliente_rua = cliente_cidade = cliente_codigo_postal = cliente_pais = False
                nome_cliente = nif_cliente = ''
                if ambas_localizacoes_internas is True:
                    nif_cliente = nif_remetente
                    nome_cliente = nome_empresa
                    cliente_rua = empresa_rua
                    cliente_cidade = empresa_cidade
                    cliente_codigo_postal = empresa_codigo_postal
                    cliente_pais = empresa_pais
                    if not picking.usar_dados_client:
                        if picking.descarga_rua and picking.descarga_cp and picking.descarga_cidade and \
                                picking.descarga_pais:
                            descarga_pais = picking.descarga_pais.code
                            descarga_rua = picking.descarga_rua or ''
                            descarga_codigo_postal = picking.descarga_cp or ''
                            descarga_cidade = picking.descarga_cidade or ''
                        else:
                            raise ValidationError(_('Falta definir os dados de descarga na aba Inf. Adicional!'))
                    else:
                        descarga_rua = cliente_rua
                        descarga_codigo_postal = cliente_codigo_postal
                        descarga_cidade = cliente_cidade
                        descarga_pais = cliente_pais

                elif picking.partner_id:
                    if picking.partner_id:
                        if not picking.partner_id.parent_id:
                            _validar_endereco('O cliente', picking.partner_id.vat, picking.partner_id.name,
                                                   picking.partner_id.street, picking.partner_id.city,
                                                   picking.partner_id.zip,picking.partner_id.country_id)

                            nif_cliente = picking.partner_id.vat or '999999999'
                            nif_cliente = nif_cliente.strip()
                            nome_cliente = picking.partner_id.name or ''
                            cliente_rua = picking.partner_id.street or picking.partner_id.street2 or ''
                            cliente_cidade = picking.partner_id.city or ''
                            cliente_codigo_postal = picking.partner_id.zip or ''
                            cliente_pais = picking.partner_id.country_id.code
                        else:
                            if picking.partner_id.parent_id:
                                _validar_endereco('A empresa do cliente', picking.partner_id.parent_id.vat,
                                                       picking.partner_id.parent_id.name,
                                                       picking.partner_id.parent_id.street,
                                                       picking.partner_id.parent_id.city,
                                                       picking.partner_id.parent_id.zip,
                                                       picking.partner_id.parent_id.country_id)
                                cliente_pais = picking.partner_id.parent_id.country_id.code

                                nif_cliente = picking.partner_id.parent_id.vat or '999999999'
                                nif_cliente = nif_cliente.strip()
                                nome_cliente = picking.partner_id.parent_id.name or ''
                                cliente_rua = picking.partner_id.parent_id.street or \
                                    picking.partner_id.parent_id.street2 or ''
                                cliente_cidade = picking.partner_id.parent_id.city or ''
                                cliente_codigo_postal = picking.partner_id.parent_id.zip or ''
                        if not picking.usar_dados_client:
                            if picking.descarga_rua and picking.descarga_cp and picking.descarga_cidade and \
                                    picking.descarga_pais:
                                descarga_rua = picking.descarga_rua or ''
                                descarga_codigo_postal = picking.descarga_cp or ''
                                descarga_cidade = picking.descarga_cidade or ''
                                descarga_pais = picking.descarga_pais.code
                            else:
                                raise ValidationError(
                                    _('Falta definir os dados de descarga na aba Inf. Adicional!'))
                        else:
                            descarga_rua = cliente_rua
                            descarga_codigo_postal = cliente_codigo_postal
                            descarga_cidade = cliente_cidade
                            descarga_pais = cliente_pais
                    else:
                        raise ValidationError(_('Falta definir o nome e o NIF do parceiro associado ao endereço.'))
                else:
                    raise ValidationError(_('A guia tem de possuir um parceiro de destino!'))

                if descarga_pais != 'PT' or cliente_pais != 'PT':
                    return True

                if not picking.data_carga:
                    if por_defeito is True:
                        agora = datetime.now()
                        delta = timedelta(minutes=por_defeito_minutos)
                        agora = agora + delta
                        picking.data_carga = str(agora)[:19]
                    else:
                        raise ValidationError(_('A guia não tem data de carga na aba Dados de Transporte!'))
                else:
                    agora = datetime.now()
                    delta = timedelta(minutes=3)
                    agora = agora + delta
                    data_de_carga = datetime.strptime(str(picking.data_carga)[:19], '%Y-%m-%d %H:%M:%S')
                    if data_de_carga < agora:
                        picking.data_carga = str(agora)[:19]
                if not picking.veiculo and por_defeito is True and por_defeito_matricula and por_defeito_matricula != '':
                    picking.veiculo = por_defeito_matricula
                linhas = ""
                for move_lines in picking.move_lines:
                    if not move_lines.order_references or doc_tipo != 'GT':
                        order_references = ''
                    else:
                        order_references = str(move_lines.order_references)
                    linhas = linhas + ' "' + move_lines.product_id.name.replace('"', '') + '" "' + \
                        str(move_lines.product_qty).replace('"', '') + '" "' + \
                        move_lines.product_uom.name.replace('"', '') + \
                        '" "0.00" "' + order_references + '"'

                self.env.cr.execute("select current_database()")

                resposta = ""

                self.message_post(body=_(resposta), subject='Erro Codigo AT')

                return self.write(resposta)
            else:
                return True

    def write(self, vals):
        if 'state' in vals:
            for stock_picking in self:
                if vals['state'] == 'done' and stock_picking.state != 'done' and stock_picking.at_status != 'success' \
                        and stock_picking.call_at is True:
                    stock_picking.callWebServiceGR(False)
                if vals['state'] == 'done' and stock_picking.state != 'done' and stock_picking.at_status != 'success' \
                        and stock_picking.call_at is False:
                    vals['at_status'] = 'validated'
        return super(StockPicking, self).write(vals)
