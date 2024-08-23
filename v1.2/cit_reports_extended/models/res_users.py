# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _default_sidebar_type(self):
        return 'invisible'

    sidebar_type = fields.Selection(
        selection=[
            ('invisible', 'Invisible'),
            ('small', 'Small'),
            ('large', 'Large')
        ],
        required=True,
        string="Sidebar Type",
        default=lambda self: self._default_sidebar_type())
