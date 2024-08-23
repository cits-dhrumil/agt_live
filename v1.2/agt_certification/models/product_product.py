# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    default_code = fields.Char(string="Internal Reference", size=60, required=True, copy=False, default='/', index=True)
    barcode = fields.Char('Barcode', copy=False, size=60, oldname='loc_barcode')

    @api.model
    def default_get(self, fields):
        defaults = super(ProductProduct, self).default_get(fields)
        defaults.update({'default_code': '/'})
        return defaults

    @api.model
    def create(self, vals):
        if vals.get('default_code', '/') == '/':
            vals['default_code'] = self.env['ir.sequence'].get('produtos.ref.seq.itc') or ''
        return super(ProductProduct, self).create(vals)

    def write(self, vals):
        if 'default_code' in vals:
            for product in self:
                if self.env['account.move.line'].sudo().search_count([('product_id', '=', product.id)]) > 0:
                    raise ValidationError(_('Este produto está incluido em documentos contabilisticos, '
                                           'pelo que não pode alterar o seu código.'))
        return super(ProductProduct, self).write(vals)

    def unlink(self):
        for product in self:
            if self.env['account.move.line'].sudo().search_count([('product_id', '=', product.id)]) > 0:
                raise ValidationError(_('Este produto está incluido em documentos contabilisticos, '
                                        'pelo que não o pode apagar, apenas arquivar.'))
        return super(ProductProduct, self).unlink()

    def copy(self, default={}):
        # self.ensure_one()

        # Craft our own `<name> (copy)` in en_US (self.copy_translation()
        # will do the other languages).
        for product_copy in self:
            context_wo_lang = product_copy.env.context.copy()
            context_wo_lang.pop('lang', None)
            product = product_copy.with_context(context_wo_lang).read(['name', 'default_code'])
            default = default.copy()
            default.update(name=_("%s (copy)") % (product[0]['name']),
                           default_code=_("%s") % (self.env['ir.sequence'].get('produtos.ref.seq.itc') or
                                                   ('copy ' + _(product[0]['default_code']))))

            if self.env.context.get('variant', False):
                fields = ['product_tmpl_id', 'active', 'variants', 'default_code',
                          'price_margin', 'price_extra']
                data = product_copy.read(fields=fields)
                for field in fields:
                    if field in default:
                        data[field] = default[field]
                data['product_tmpl_id'] = data.get('product_tmpl_id', False) and data['product_tmpl_id'][0]
                del data['id']
                return product_copy.create(data)
            else:
                return super(ProductProduct, self).copy(default=default)

    @api.constrains('default_code', 'company_id')
    def _check_default_code(self):
        for product in self:
            products_code_count = self.sudo().search_count([('id', '!=', product.id),
                                                            ('default_code', '=',
                                                             product.default_code),
                                                            '|', ('company_id', '=',
                                                                  product.company_id.id),
                                                            ('company_id', '=', False)])
            if products_code_count > 0:
                raise ValidationError(_("Product code must be unique, per company!"))


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # default do campo "tipo_produto_id"
    @api.model
    def _get_field_name_default(self):
        tipo_produto = self.env['tipo.produto.saft'].search([('code', '=', 'M')])
        if tipo_produto:
            return tipo_produto
        return self.env['tipo.produto.saft']

    property_account_refund_income_id = fields.Many2one('account.account', company_dependent=True,
                                                        string="Customer Credit Notes Account",
                                                        domain=[('deprecated', '=', False)],
                                                        help="Account used by default in customer credit notes.")

    property_account_refund_expense_id = fields.Many2one('account.account', company_dependent=True,
                                                         string="Credit Note Account Suppliers",
                                                         domain=[('deprecated', '=', False)],
                                                         help="Account used by default in customer credit notes.")

    tipo_produto_id = fields.Many2one('tipo.produto.saft', string='Saft Product Type', copy=False,
                                      default=_get_field_name_default)
