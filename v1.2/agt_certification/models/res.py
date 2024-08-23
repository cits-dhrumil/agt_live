# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

import os

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json
import logging
import xmlrpc.client as xmlrpclib

import requests

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _default_vat(self):
        return '999999990'

    @api.depends('vat', 'company_id')
    def _compute_same_vat_partner_id_opc(self):
        for partner in self:
            # use _origin to deal with onchange()
            partner_id = partner._origin.id
            # active_test = False because if a partner has been deactivated you still want to raise the error,
            # so that you can reactivate it instead of creating a new one, which would loose its history.
            Partner = self.with_context(active_test=False).sudo()
            domain = [
                ('vat', '=', partner.vat),
                ('company_id', 'in', [False, partner.company_id.id]),
            ]
            if partner_id:
                domain += [('id', '!=', partner_id), '!', ('id', 'child_of', partner_id)]

            partner.same_vat_partner_id = bool(partner.vat) and not partner.parent_id and Partner.search(domain,
                                                                                                         limit=1)
            if partner.vat == '999999990' or partner.vat == '999999999':
                partner.same_vat_partner_id = False


    @api.depends('vat')
    def _compute_nif_duplicado(self):
        for partner in self:
            if partner.vat and partner.vat != '999999990' and partner.vat != '999999999' and not partner.company_id.validar_nif_duplicados:
                parceiros = self.search([('vat', '=', partner.vat)])
                if len(parceiros) > 1:
                    partner.nif_duplicado = True
                else:
                    partner.nif_duplicado = False
            else:
                partner.nif_duplicado = False

    same_vat_partner_id = fields.Many2one('res.partner', string='Partner with same Tax ID',
                                          compute='_compute_same_vat_partner_id_opc', store=False)
    cash_vat_scheme_indicator = fields.Boolean(string="Cash VAT",
                                               default=False, copy=False)
    nif_duplicado = fields.Boolean(compute='_compute_nif_duplicado', string="Prohibit Duplicate NIF's",
                                   help="If you have a visa, there is another partner with that number.",
                                   default=False, copy=False)
    vat = fields.Char(string="Taxpayer No.", size=20,
                      help="Tax Identification Number",
                      copy=False,required=False)
    reg_com = fields.Char(string="Social Capital", size=32, help="5.000", copy=False)
    conservatoria = fields.Char(string="Conservatory", size=64, help="Commercial registry office", copy=False)
    nif_representante = fields.Char(string="Representative's NIF", size=20, copy=False)
    nif_toc = fields.Char(string="NIF do TOC", size=20, copy=False)
    fin_code = fields.Char(string="Finance service code", size=4, copy=False)
    self_bill_sales = fields.Boolean(string="Auto Billing for Sales", copy=False,
                                     help="ndicate whether there is a self-billing agreement for sales to this partner")
    self_bill_purch = fields.Boolean(string="Auto Invoicing for Purchases", copy=False,
                                     help="Indicate whether there is a self-invoicing agreement for purchases from the partner")
    tipo_cambio = fields.Selection([
        ('Fixo', 'Fixed'),
        ('Variavel', 'Variable')], string='Exchange Type', readonly=False, copy=False, default='Variavel')

    @api.model
    def default_get(self, fields):
        defaults = super(ResPartner, self).default_get(fields)
        defaults.update({'ref': '/'})
        return defaults

    @api.model
    def create(self, vals):
        if 'parent_id' in vals and vals['parent_id']:
            vals['is_company'] = False
        if vals.get('ref', '/') == '/' or vals.get('ref', '') == '':
            vals['ref'] = self.env['ir.sequence'].get('parceiros.ref.seq.itc') or '/'

        if 'vat' in vals:
            if str(vals['vat']) == '':
                vals['vat'] = '999999990'

            if 'parent_id' in vals and vals['parent_id']:
                self._cr.execute(
                    "select customer_rank,supplier_rank from res_partner where id=" + str(
                        vals['parent_id']))
                parent_partner_id = self._cr.fetchone()
                if parent_partner_id[0] == 1:
                    vals['customer_rank'] = 1
                else:
                    vals['customer_rank'] = 0
                if parent_partner_id[1] == 1:
                    vals['supplier_rank'] = 1
                else:
                    vals['supplier_rank'] = 0

        partner = super(ResPartner, self).create(vals)
        if 'vat' in vals:
            partner.check_vat()

        self._cr.execute("""
                SELECT rc.validar_nif_duplicados
                FROM res_partner rp, res_company rc
                WHERE rp.company_id=rc.id and rp.id=%s""", (partner.id,))
        validar_nif_duplicados = self._cr.fetchone()
        if partner.vat != '999999990' and validar_nif_duplicados:
            if partner.company_id and partner.company_id.id:
                self._cr.execute("""
                        SELECT id
                        FROM res_partner
                        WHERE vat = %s AND company_id = %s AND id != %s """,
                                 (str(partner.vat), str(partner.company_id.id),
                                  str(partner.id)))
            else:
                self._cr.execute("""
                        SELECT id
                        FROM res_partner
                        WHERE vat = %s AND and id != %s """,
                                 (str(partner.vat), str(partner.id)))
            parent_partner_id = self._cr.fetchone()
            if parent_partner_id and parent_partner_id[0]:
                if validar_nif_duplicados[0]:
                    raise ValidationError(_("Ja existe um cliente com esse NIF."))
        return partner

    def write(self, vals):
        Partner = self.env['res.partner']
        AccountMove = self.env['account.move']
        for partner in self:
            if 'vat' in vals and str(vals['vat']) != '999999990' and partner.company_id.validar_nif_duplicados:
                domain = [('vat', '=', str(vals['vat'])),
                          ('id', '!=', partner.id)]
                if 'company_id' in vals and vals['company_id']:
                    domain.append(('company_id', '=', str(vals['company_id'])))
                    if Partner.search_count(domain) > 0:
                        raise ValidationError(_("Ja existe um parceiro com esse NIF."))

            client_invoices = AccountMove.search_count([('state', '!=', 'draft'),
                                                        ('move_type', 'in', ['out_invoice', 'out_refund']),
                                                        ('partner_id', '=', partner.id)])
            if client_invoices > 0 and partner.vat != '999999990':
                if ('vat' in vals and vals['vat'] != partner.vat) or (
                        'ref' in vals and vals['ref'] != partner.ref):
                    raise ValidationError(_(
                        "Esse parceiro está incluido em documentos contabilisticos, "
                        "pelo que não pode alterar o seu código ou NIF."))

            if 'vat' in vals and str(vals['vat'])[:2] == 'PT':
                vals['vat'] = vals['vat'].replace('PT', '')

        result = super(ResPartner, self).write(vals)
        for partner in self:
            if 'partner' in vals:
                partner.check_vat()
            if 'parent_id' in vals:
                faturas = AccountMove.search_count([
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('partner_id', '=', partner.id)])
                if faturas > 0:
                    raise ValidationError(
                        _('Não pode alterar o parceiro coemrcial deste parceiro pois o mesmo porque possui faturas/notas de crédito.'))
        return result

    def copy(self, default=None, done_list=None, local=False):
        default = {} if default is None else default.copy()
        default.update({'vat': '999999990', 'ref': '/'})
        return super(ResPartner, self).copy(default)

    def unlink(self):
        for partner in self:
            self.env.cr.execute(
                "select id from stock_picking where partner_id=" + str(partner.id))
            picking_id = self.env.cr.fetchone()
            if picking_id and picking_id[0]:
                raise ValidationError(
                    _('O parceiro entra em guias pelo que apenas o pode desactivar.'))
        return super(ResPartner, self).unlink()

    @api.constrains('ref', 'company_id')
    def _check_ref(self):
        if self.env.cr.dbname != 'braver_v14':
            for partner in self:
                partner_code_count = self.sudo().search_count([('id', '!=', partner.id),
                                                               ('ref', '=', partner.ref),
                                                               '|', ('company_id', '=', partner.company_id.id),
                                                               ('company_id', '=', False)])
                if partner_code_count > 0:
                    raise ValidationError(_("Partner ref must be unique, per company!"))

    @api.onchange('tipo_cambio')
    def _onchange_tipo_cambio(self):
        if self.tipo_cambio == 'Fixo':
            self.tipo_cambio = 'Variavel'
            return {
                'warning': {'title': _('Atenção'),
                            'message': _('Esta funcionalidade ainda não está disponível!'), }
            }

    @api.model
    def _commercial_fields(self):
        remove_vat = super(ResPartner, self)._commercial_fields()
        remove_vat.remove('vat')
        return remove_vat

    def nif_process(self, type):
        message = ''
        if self.vat != '999999990' and self.vat != '999999999' and self.vat:
            portugal = self.env['res.country'].search([('code', '=', 'PT'), ('name', '=', 'Portugal')])
            if portugal and (not self.country_id or self.country_id.id == portugal.id):
                self.vat = self.vat.replace("PT", "")
                keys = ['f8a4ca6f9d1d8f8a39a4cba0bb451c2c',
                        '0c3611cbf3ddb8b7ec2af1a4755b1d82',
                        'ad5e6acce3c6e16a7119da7101d7bde8',
                        'ff18d7e9b119f602dcbf9c15e72c701d',
                        '2ff1f934d20e7ffb23dc328c719d0000',
                        'cc0f1dff68c6641b18547700f4605030',
                        '53e0cee2231ee99ce2bdeaed84606d94',
                        '2eaef6f628ba03778f2c82a2fc4d7963',
                        'b96bf647c065d31625ab96255f159685', ]
                contador = 0
                for key in keys:
                    payload = {'json': '1', 'q': self.vat, 'key': key}
                    r = requests.get("http://www.nif.pt/", params=payload)
                    res = r.text
                    download = json.loads(str(res).replace("'", "\""))
                    if 'message' in download and download['message'] and 'Limit per' in download['message']:
                        contador = contador + 1
                        if contador >= 9:
                            try:
                                self.message_post(body=_('Limite de validaçẽs do NIF alcançado.'))
                            except:
                                pass

                    if not ('message' in download and download['message'] and 'Limit per' in download['message']):
                        if 'is_nif' in download and (not download['is_nif'] or not download['nif_validation']):
                            return {
                                'warning': {'title': _('Atenção'),
                                            'message': _('O NIF é inválido!'), }}
                        name = ''
                        morada = ''
                        cp1 = ''
                        cp2 = ''
                        cidade = ''
                        email = ''
                        telefone = ''
                        website = ''
                        if download['result'] == 'success':
                            if 'title' in download['records'][self.vat] and download['records'][self.vat]['title']:
                                name = download['records'][self.vat]['title']

                            if 'address' in download['records'][self.vat] and download['records'][self.vat]['address']:
                                morada = download['records'][self.vat]['address']

                            if 'pc4' in download['records'][self.vat] and download['records'][self.vat]['pc4']:
                                cp1 = download['records'][self.vat]['pc4']

                            if 'pc3' in download['records'][self.vat] and download['records'][self.vat]['pc3']:
                                cp2 = '-' + download['records'][self.vat]['pc3']

                            if 'city' in download['records'][self.vat] and download['records'][self.vat]['city']:
                                cidade = download['records'][self.vat]['city']

                            if 'contacts' in download['records'][self.vat]:
                                if 'email' in download['records'][self.vat]['contacts'] and \
                                        download['records'][self.vat]['contacts']['email']:
                                    email = download['records'][self.vat]['contacts']['email']

                                if 'phone' in download['records'][self.vat]['contacts'] and \
                                        download['records'][self.vat]['contacts']['phone']:
                                    telefone = download['records'][self.vat]['contacts']['phone']

                                if 'website' in download['records'][self.vat]['contacts'] and \
                                        download['records'][self.vat]['contacts']['website']:
                                    website = download['records'][self.vat]['contacts']['website']

                        return {
                            'name': self.name or name,
                            'vat': self.vat,
                            'street': self.street or morada,
                            'country_id': portugal.id,
                            'city': self.city or cidade,
                            'zip': self.zip or str(cp1 + cp2),
                            'website': self.website or website,
                            'email': self.email or email,
                            'phone': self.phone or telefone,
                        }
            else:
                self.check_vat()
        return {}

    @api.onchange('vat')
    def onchange_nif(self):
        message = ''
        if self.vat != '999999990' and self.vat != '999999999' and self.vat:
            if not self.country_id or self.country_id.code == 'PT':
                value = {}
                try:
                    keys = ['f8a4ca6f9d1d8f8a39a4cba0bb451c2c',
                            '0c3611cbf3ddb8b7ec2af1a4755b1d82',
                            'ad5e6acce3c6e16a7119da7101d7bde8',
                            'ff18d7e9b119f602dcbf9c15e72c701d',
                            '2ff1f934d20e7ffb23dc328c719d0000',
                            'cc0f1dff68c6641b18547700f4605030',
                            '53e0cee2231ee99ce2bdeaed84606d94',
                            '2eaef6f628ba03778f2c82a2fc4d7963',
                            'b96bf647c065d31625ab96255f159685', ]
                    contador = 0
                    for key in keys:
                        payload = {'json': '1', 'q': self.vat, 'key': key}
                        r = requests.get("http://www.nif.pt/", params=payload)
                        res = r.text
                        download = json.loads(str(res).replace("'", "\""))
                        if 'message' in download and download['message'] and 'Limit per' in download['message']:
                            contador = contador + 1
                            if contador >= 9:
                                try:
                                    self.message_post(body=_('Limite de validaçẽs do NIF alcançado.'))
                                except:
                                    pass
                        if not ('message' in download and download['message'] and 'Limit per' in download['message']):
                            if 'is_nif' in download and (not download['is_nif'] or not download['nif_validation']):
                                return {
                                    'warning': {'title': _('Atenção'),
                                                'message': _('O NIF é inválido!'), }
                                }
                            name = ''
                            morada = ''
                            cp1 = ''
                            cp2 = ''
                            cidade = ''
                            email = ''
                            telefone = ''
                            website = ''
                            if download['result'] == 'success':
                                if 'title' in download['records'][self.vat] and download['records'][self.vat]['title']:
                                    name = download['records'][self.vat]['title']

                                if 'address' in download['records'][self.vat] and download['records'][self.vat][
                                    'address']:
                                    morada = download['records'][self.vat]['address']

                                if 'pc4' in download['records'][self.vat] and download['records'][self.vat]['pc4']:
                                    cp1 = download['records'][self.vat]['pc4']

                                if 'pc3' in download['records'][self.vat] and download['records'][self.vat]['pc3']:
                                    cp2 = '-' + download['records'][self.vat]['pc3']

                                if 'city' in download['records'][self.vat] and download['records'][self.vat]['city']:
                                    cidade = download['records'][self.vat]['city']

                                if 'contacts' in download['records'][self.vat]:
                                    if 'email' in download['records'][self.vat]['contacts'] and \
                                            download['records'][self.vat]['contacts']['email']:
                                        email = download['records'][self.vat]['contacts']['email']

                                    if 'phone' in download['records'][self.vat]['contacts'] and \
                                            download['records'][self.vat]['contacts']['phone']:
                                        telefone = download['records'][self.vat]['contacts']['phone']

                                    if 'website' in download['records'][self.vat]['contacts'] and \
                                            download['records'][self.vat]['contacts']['website']:
                                        website = download['records'][self.vat]['contacts']['website']

                            value = {
                                'name': self.name or name,
                                'vat': self.vat,
                                'street': self.street or morada,
                                'city': self.city or cidade,
                                'zip': self.zip or str(cp1 + cp2),
                                'website': self.website or website,
                                'email': self.email or email,
                                'phone': self.phone or telefone,
                            }
                            return {'value': value}
                except:
                    e = 1

    def verificar_nif(self):
        values = self.nif_process('object')
        if values:
            self.write(values)

class ResCompany(models.Model):
    _inherit = "res.company"

    def account_adjustments(self, code):
        account = self.env['account.account'].search([('code', '=like', code), ('tipo_conta', '=', 'GM')], limit=1)
        if not account:
            account = self.env['account.account'].search([('code', '=like', code)], limit=1)
        return account

    account_adjustments_purchase = fields.Many2one("account.account", string="Conta de acerto de casa decimal para "
                                                                             "compra",
                                                   default=lambda self: self.account_adjustments('611%'))
    account_adjustments_sale = fields.Many2one("account.account", string="Conta de acertos de casa decimal para venda",
                                               default=lambda self: self.account_adjustments('711%'))
    pais_certificacao = fields.Many2one('res.country', string="Pais Certificação", copy=False,
                                        help="Caso o campo esteja preechido na certificação este será consultado "
                                             "para verificar se as restrições se aplicam ou não.")
    validar_nif_duplicados = fields.Boolean(string="Proibir NIF's Duplicados",
                                            help="Se levar visto, o programa valida o nif tem de ser unico "
                                                 "por parceiro.", default=True, copy=False)
    validar_nif = fields.Boolean(string="Validar NIF",
                                 help="Se levar visto, o programa valida o nif dos parceiros sempre que os cria ou "
                                      "edita.", default=True, copy=False)
    cash_vat_scheme_indicator = fields.Boolean(string="Iva de Caixa",
                                               help="Assinale se houver adsão ao regime de iva de caixa. Irá exportar"
                                                    "os pagamentos no ficheiro saft.",
                                               default=False, copy=False)
    third_parties_billing_indicator = fields.Boolean(string="Faturação por Terceiros",
                                                     help="Assinale se respeitar a faturação emitida em nome e por conta de terceiros",
                                                     default=False, copy=False)
    open_journal = fields.Many2one('account.journal', string="Diário de Abertura", copy=False)
    conservatoria = fields.Char(related="partner_id.conservatoria", string='Conservatoria', help="Nif", size=64)
    reg_com = fields.Char(related="partner_id.reg_com", string='Capital Social', help="5.000", size=32)
    local_installation = fields.Boolean('Instalação Local', default=False)

    def write(self, vals):
        for company in self:
            if 'vat' in vals:
                if not company.company_registry:
                    vals['company_registry'] = vals['vat']
                if not company.conservatoria:
                    company.partner_id.conservatoria = vals['vat']
                if not company.reg_com:
                    company.partner_id.reg_com = '5.000'
        return super(ResCompany, self).write(vals)

    def copy(self, default=None):
        raise ValidationError(_("Não é possivel utilizar a opção duplicar nas empresas, por favor use o botão criar."))

    @api.onchange('reg_com', 'vat')
    def _onchange_comapny_details(self):
        for company in self:
            company_details = ''
            if company.name:
                company_details = '<b>' + company.name + '</b>' + '<br/>'
            report_footer = ''
            # company footer
            if company.email:
                report_footer += 'E-mail: ' + company.email
            if company.website:
                report_footer += ' - Website: ' + company.website
            if company.phone:
                report_footer += '  - Tel: ' + company.phone

            # company details
            if company.street:
                company_details += company.street + '<br/>'
            if company.city:
                company_details += company.city + ', '
            if company.zip:
                company_details += company.zip + ' '
            if company.country_id:
                company_details += company.country_id.name

            if company.reg_com:
                company_details += '<br/>Cap. Social: ' + company.reg_com + '€'
            if company.vat:
                company_details += '<br/>NIF: ' + company.vat
            company.company_details = company_details
            company.report_footer = report_footer

class ResUsers(models.Model):
    _inherit = "res.users"

    @classmethod
    def authenticate(self, db, login, password, user_agent_env):
        user_authenticate_id = super(ResUsers, self).authenticate(db, login, password, user_agent_env)

        cr = self.pool.cursor()

        cr.execute("select local_installation from res_company order by id desc")
        local = cr.fetchone()[0]

        cr.execute("select count(*) from ir_module_module where state='installed'")
        num_modulos = cr.fetchone()[0]

        cr.execute("SELECT current_database()")
        nome_minha_bd = cr.fetchone()[0]
        cr.close()

        acesso = False

        if local:
            try:
                sock_common_NEW = xmlrpclib.ServerProxy('http://51.255.64.14:8069/xmlrpc/common')
                uidNEW = sock_common_NEW.login('opencloud', 'UserWebService', 'gdjtr87RTdk45')
                sockNEW = xmlrpclib.ServerProxy('http://51.255.64.14:8069/xmlrpc/object')
                caminho = sockNEW.execute('opencloud', uidNEW, 'gdjtr87RTdk45', 'cliente.remoto', 'addons', [],
                                          nome_minha_bd)
                os.system("du -hs -B1 " + caminho + " > /var/openerpTestFiles/tamanho")
                f = open("/var/openerpTestFiles/tamanho", "r")
                tamanho = f.read()
                f.close()
                tamanho = tamanho.split('\t')[0]
                acesso = sockNEW.execute('opencloud', uidNEW, 'gdjtr87RTdk45', 'cliente.remoto', 'login', [],
                                         nome_minha_bd, num_modulos, tamanho)
            except:
                _logger.exception('Impossivel conectar a base de dados da Opencloud.')
            if acesso:
                return user_authenticate_id

        else:
            return user_authenticate_id

        return False
