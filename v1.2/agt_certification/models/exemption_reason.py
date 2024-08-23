# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api, _
from odoo.osv import expression


class ExemptionReason(models.Model):
    _name = "exemption.reason"
    _description = 'Motivo de Isenção'

    name = fields.Char(string="Reason", required=True, copy=False)
    code = fields.Char(string="Code", required=True, copy=False)
    article = fields.Char(string="Article", copy=False)
    discontinued = fields.Boolean(string="Discontinued", copy=False)
    display_name = fields.Char(compute='_compute_display_name', compute_sudo=True)

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=100, order=None):
        domain = []
        if name:
            domain = ['|', ('code', 'ilike', name), ('name', 'ilike', name)]
        return self._search(expression.AND([domain]), limit=limit, order=order)

    def _compute_display_name(self):
        for reason in self:
            result = []
            name = '[' + _(reason.code) + '] ' + _(reason.name)
            result.append((reason.id, name))
            reason.display_name = name
