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


class AccountTax(models.Model):
    _inherit = "account.tax"

    description = fields.Char(string='Label on Invoices', required=True)
    autoliquidacao = fields.Boolean(string="Self-Settlement")
    country_region = fields.Selection([('PT', 'Continente'), ('PT-AC', 'Açores'), ('PT-MA', 'Madeira')],
                                      string="Fiscal Space", required=True, default='PT', copy=False)
    saft_tax_type = fields.Selection([
        ('IVA', 'IVA'),
        ('IS', 'Seal Imp'),
        ('NS', 'No Subject')
    ], string="Tax", required=True, default='IVA', copy=False)
    saft_tax_code = fields.Selection([('RED', 'Reduced'),
                                      ('NOR', 'Normal'),
                                      ('INT', 'Intermediate'),
                                      ('ISE', 'Exempt'),
                                      ('OUT', 'Out'),
                                      ('NS', 'Not Subject')], string="Rate Level",
                                     required=True, default='NOR', copy=False)
    expiration_date = fields.Date(string="Expiration Date", copy=False)
    exemption_reason = fields.Many2one("exemption.reason", string="Exemption Reason", copy=False)

    def unlink(self):
        for tax in self:
            tax._validar_imposto_utilizado(
                _("Esse imposto está incluído em documentos contabilisticos, pelo que não "
                  "pode eliminá-lo."))
        return super(AccountTax, self).unlink()

    def _validar_imposto_utilizado(self, aviso):
        for tax in self:
            taxes_count = self.env['account.move.line'].sudo().search_count(
                [('tax_ids', 'in', [tax.id]),
                 ('company_id', '=', tax.company_id.id)])
            if taxes_count:
                raise ValidationError(aviso)

    def name_get(self):
        # if the tax is zero and has exemption reason, display the exemption reason and tax name on tax name
        res = []
        for tax in self:
            if tax.amount == 0 and tax.exemption_reason and tax.type_tax_use == 'sale':
                res.append((tax.id, '[' + tax.exemption_reason.code + '] ' +
                            tax.exemption_reason.name + ' - ' + tax.name))
            else:
                res.append((tax.id, tax.name))
        return res

    def configure_account_tax_group_and_saft_code(self):
        for tax in self:
            try:
                if str(tax.amount)[:2] == '23':
                    tax.saft_tax_code = 'NOR'
                    tax.tax_group_id = self.env['ir.model.data'].check_object_reference('l10n_pt', 'tax_group_iva_23')[1]
                elif str(tax.amount)[:2] == '13':
                    tax.saft_tax_code = 'INT'
                    tax.tax_group_id = self.env['ir.model.data'].check_object_reference('l10n_pt', 'tax_group_iva_13')[1]
                elif str(tax.amount)[:1] == '6':
                    tax.saft_tax_code = 'RED'
                    tax.tax_group_id = self.env['ir.model.data'].check_object_reference('l10n_pt', 'tax_group_iva_6')[1]
                elif str(tax.amount)[:1] == '0':
                    tax.saft_tax_code = 'ISE'
                    tax.tax_group_id = self.env['ir.model.data'].check_object_reference('l10n_pt', 'tax_group_iva_0')[1]
                else:
                    tax.saft_tax_code = 'OUT'
                    tax.tax_group_id = self.env['ir.model.data'].check_object_reference('opc_certification', 'tax_group_retencao')[1]
            except:
                e = 1

    def _validar_imposto(self, vals):
        for tax in self:
            tax_name = tax.name
            if 'name' in vals:
                tax_name = vals['name']
            type_tax_use = tax.type_tax_use
            if 'type_tax_use' in vals:
                type_tax_use = vals['type_tax_use']
            tax_count = self.sudo().search_count([('name', '=', tax_name),
                                                  ('type_tax_use', '=', type_tax_use),
                                                  ('company_id', '=', tax.company_id.id),
                                                  ('id', '!=', tax.id)])
            if tax_count > 0:
                raise ValidationError(
                    _("Não pode ter dois impostos na mesma empresa com o mesmo nome e tipo de uso."))

            amount = tax.amount
            if 'amount' in vals:
                amount = vals['amount']
            exemption_reason = tax.exemption_reason
            tax_type_use = tax.type_tax_use
            if 'exemption_reason' in vals:
                exemption_reason = vals['exemption_reason']
            if 'type_tax_use' in vals:
                tax_type_use = vals['type_tax_use']
            if amount == 0 and not exemption_reason and tax_type_use == 'sale':
                # add first exemption found to the tax
                exemption_reason = self.env['exemption.reason'].search([], limit=1)
                if exemption_reason:
                    if 'exemption_reason' in vals:
                        vals['exemption_reason'] = exemption_reason.id
                    else:
                        vals['exemption_reason'] = exemption_reason.id
                else:
                    raise ValidationError(_("Impostos isentos tem de ter um motivo de isenção."))
            if amount != 0 and exemption_reason:
                raise ValidationError(_("Não pode ter impostos com valor diferente de 0 e preenchido o campo "
                                        "(Motivo da isenção) na aba (Dados SAFT)."))

            if 'amount' in vals:
                tax._validar_imposto_utilizado(_("Esse imposto está incluído em documentos contabilisticos, pelo que "
                                                 "não pode alterar o seu montante ou se ele esta ou nao incluido no "
                                                 "preco. Para proceder a estas alterações por favor crie um novo "
                                                 "imposto."))
