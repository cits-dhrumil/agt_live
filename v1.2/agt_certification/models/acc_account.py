# -*- coding: utf-8 -*-
##############################################################################
#                                                                            #
# Part of Caret IT Solutions Pvt. Ltd. (Website: www.caretit.com).           #
# See LICENSE file for full copyright and licensing details.                 #
#                                                                            #
##############################################################################

from odoo import models, fields, api


class AccountAccount(models.Model):
    _inherit = "account.account"

    # Update parent accounts
    # Menu: Accounting - Configuration - Chart of Accounts
    def init(self):
        for account in self.env['account.account'].sudo().search([]):
            # if not l.parent_id:
            account.sudo()._compute_parent_id()

    active = fields.Boolean(string="Active", default=True)
    tipo_conta = fields.Selection(selection=[('GR', 'GR - 1st degree account of general accounting'),
                                             ('GA', 'GA - General ledger aggregating or integrating account'),
                                             ('GM', 'GM - General ledger movement account'),
                                             ('AR', 'AR - 1st degree account of analytical accounting'),
                                             ('AA',
                                              'AA - Analytical accounting aggregator or integrator account'),
                                             ('AM', 'AM - Analytical accounting movement account')],
                                  string="Account Group", required=True, default="GM", copy=False)
    parent_id = fields.Many2one('account.account', compute='_compute_parent_id', string="Father Account", store=True)
    children_ids = fields.One2many('account.account', 'parent_id', 'Accounts')
    taxonomia_id = fields.Many2one('taxonomia', string='Taxonomia')
    code = fields.Char(size=10, required=True, index=True)
    balance_with_context = fields.Float(compute='_compute_balance_with_context', string="Balance Between Dates")

    # update parent account if it exists
    @api.depends('code', 'tipo_conta')
    def _compute_parent_id(self):
        for account in self:
            if account.code:
                ids_pai = []
                for i in range(1, 10):
                    ids_pai = self.env['account.account'].search(
                        [('code', '=', account.code[:-i]),
                         ('company_id', '=', account.company_id.id)], limit=1)
                    if len(ids_pai) > 0:
                        break

                account.parent_id = ids_pai.id

    # update account type to GR if parent account is changed to empty
    # update parent account if it exists
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'code' in vals:
                for i in range(1, 10):
                    ids_pai = self.env['account.account'].search(
                        [('code', '=', vals['code'][:-i])], limit=1)
                    for ids_pais in ids_pai:
                        vals['parent_id'] = ids_pais.id
                        break
            if 'parent_id' in vals and vals['parent_id'] is False:
                vals['tipo_conta'] = "GR"
        current_account = super(AccountAccount, self).create(vals_list)
        for vals in vals_list:
            if 'parent_id' in vals and vals['parent_id']:
                self._cr.execute("""
                    UPDATE account_account
                    SET tipo_conta='GA'
                    WHERE coalesce(parent_id,-1)<>-1 and id=""" + str(
                    vals['parent_id']))
                self.env.cr.execute("""
                            select id
                            from account_account
                            where code ilike %s and parent_id = %s and id !=%s
                            """, (
                current_account.code + '%', current_account.parent_id.id,
                current_account.id))
                accounts = self.search([
                    ('id', 'in', list(self.env.cr.fetchall()))])
                for account in accounts:
                    account.write({'parent_id': current_account.id})
        return current_account

    def write(self, vals):
        if 'parent_id' in vals and vals['parent_id'] is False:
            vals['tipo_conta'] = "GR"
        result = super(AccountAccount, self).write(vals)
        if 'parent_id' in vals and vals['parent_id']:
            self._cr.execute("""
                UPDATE account_account
                SET tipo_conta='GA'
                WHERE coalesce(parent_id,-1)<>-1 and id=""" + str(vals['parent_id']))
            self.env.cr.execute("""
                select id
                from account_account
                where code ilike %s and parent_id = %s and id !=%s
                """, (self.code + '%', self.parent_id.id, self.id))
            accounts = self.search([
                ('id', 'in', list(self.env.cr.fetchall()))])
            for account in accounts:
                account.write({'parent_id': self.id})
        return result

    def _compute_balance_with_context(self):
        domain = [('account_id', 'in', self.ids)]
        context = dict(self._context or {})
        if context.get('date_start_filter'):
            domain += [('date', '>=', context['date_start_filter'])]
        if context.get('date_end_filter'):
            domain += [('date', '<=', context['date_end_filter'])]
        balances = {
            read['account_id'][0]: read['balance']
            for read in self.env['account.move.line'].read_group(
                domain=domain,
                fields=['balance', 'account_id'],
                groupby=['account_id'],
            )
        }
        for record in self:
            record.balance_with_context = balances.get(record.id, 0)

    def has_moves(self, date_start=None, date_end=None):
        """Check if the account has posted moves in the given period. If no period is given, check if the account has
        any move.
        """
        self.ensure_one()
        domain = [('account_id', '=', self.id), ('parent_state', '=', 'posted')]
        if date_start:
            domain.append(('date', '>=', date_start))
        if date_end:
            domain.append(('date', '<=', date_end))
        return self.env['account.move.line'].search_count(domain) > 0

    def get_billing_ledger_account(self):
        """Recursively get the parent account, until there is no parent.
        :return: account.account record
        """
        self.ensure_one()
        if self.parent_id:
            return self.parent_id.get_billing_ledger_account()
        if self.tipo_conta == 'GR':
            return self
        return

    def get_period_vals(self, parents, date_from, date_to, method, company_id):
        opening_move_domain = [
            ('parent_state', '=', 'posted'),
            ('account_id', 'in', [self.id] + self.children_ids.ids) if self in parents else ('account_id', '=', self.id)
        ]

        period_move_domain = [
            ('parent_state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('account_id', 'in', [self.id] + self.children_ids.ids) if self in parents else ('account_id', '=', self.id)
        ]

        if method == 'first_record':
            move_id = self.env['account.move'].search([
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('state', '=', 'posted'),
                ('company_id', '=', company_id.id),
            ], order='date', limit=1)

            opening_move_domain.append(('move_id', '=', move_id.id))
            period_move_domain.append(('move_id', '!=', move_id.id))

        else:
            opening_move_domain.append(('date', '<', date_from))

        opening_move_lines = self.env['account.move.line'].search(opening_move_domain)
        period_move_lines = self.env['account.move.line'].search(period_move_domain)

        opening_credit = sum(opening_move_lines.mapped('credit'))
        opening_debit = sum(opening_move_lines.mapped('debit'))
        closing_credit = opening_credit + sum(period_move_lines.mapped('credit'))
        closing_debit = opening_debit + sum(period_move_lines.mapped('debit'))

        return {
            'opening_credit': opening_credit,
            'opening_debit': opening_debit,
            'closing_credit': closing_credit,
            'closing_debit': closing_debit,
        }

    def configure_grouping_category(self):
        """Configure the grouping category of the account to use in the field 2.1.7 of the SAFT file."""
        for account in self:
            if len(account.code) <= 2:
                account.tipo_conta = 'GR'
            elif account.has_moves() or not account.children_ids:
                account.tipo_conta = 'GM'
            elif account.children_ids and not self.env['account.move.line'].search([('account_id', '=', account.id)]):
                account.tipo_conta = 'GA'