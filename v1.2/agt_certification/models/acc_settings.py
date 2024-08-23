# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields


class AccountConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"
    _description = 'This class is created with the aim of creating 2 new fields in the accounting settings' \
                   'these two fields are used to calculate decimal cases,' \
                   'both purchases and sales are configurable.'

    account_adjustments_purchase = fields.Many2one("account.account", related='company_id.account_adjustments_purchase',
                                                   string="Decimal adjustment account for purchase")
    account_adjustments_sale = fields.Many2one("account.account", string="Decimal adjustments account for sale",
                                               related='company_id.account_adjustments_sale')
    line_per_page = fields.Integer()

    def set_values(self):
        super(AccountConfigSettings, self).set_values()
        lines = self.line_per_page
        param = self.env['ir.config_parameter'].sudo()
        param.set_param('agt_certification.line_per_page', lines)

    def get_values(self):
        res = super(AccountConfigSettings, self).get_values()
        res.update(
            line_per_page=int(self.env['ir.config_parameter'].sudo().get_param('agt_certification.line_per_page'), ))
        return res
