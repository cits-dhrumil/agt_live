# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    n_copies_picking = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('6', '6'),
                                         ('7', '7'), ('8', '8'), ('9', '9'), ('10', '10')],
                                        string='Number of Copies for Picking',
                                        default='3')
    n_copies_invoice = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('6', '6'),
                                         ('7', '7'), ('8', '8'), ('9', '9'), ('10', '10')],
                                        string='Number of Copies for invoice and payment',
                                        default='3')
    background_image = fields.Binary(
        string="Apps Menu Background Image",
        attachment=True)
    default_sidebar_preference = fields.Selection(
        selection=[
            ('invisible', 'Invisible'),
            ('small', 'Small'),
            ('large', 'Large')
        ],
        string="Sidebar Type",
        default='invisible')


