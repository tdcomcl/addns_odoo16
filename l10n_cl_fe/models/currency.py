from odoo import api, fields, models
from odoo.tools import float_round

from odoo.addons import decimal_precision as dp


def float_round_custom(value, precision_digits=None, precision_rounding=None, rounding_method="HALF-UP"):
    result = float_round(value, precision_digits, precision_rounding, rounding_method)
    if precision_rounding == 1 or (precision_digits is not None and precision_digits == 0):
        return int(result)
    return result


class ResCurrency(models.Model):
    _inherit = "res.currency"

    code = fields.Char(string="Código",)
    abreviatura = fields.Char(string="Abreviatura",)
    rate = fields.Float(
        compute="_compute_current_rate",
        string="Current Rate",
        digits=dp.get_precision("Currency Rate"),
        help="The rate of the currency to the currency of rate 1.",
    )
    rounding = fields.Float(string="Rounding Factor", digits=(12, 14), default=0.01)

    
    def round(self, amount):
        """Return ``amount`` rounded  according to ``self``'s rounding rules.

           :param float amount: the amount to round
           :return: rounded float
        """
        # TODO: Need to check why it calls round() from sale.py, _amount_all() with *No* ID after below commits,
        # https://github.com/odoo/odoo/commit/36ee1ad813204dcb91e9f5f20d746dff6f080ac2
        # https://github.com/odoo/odoo/commit/0b6058c585d7d9a57bd7581b8211f20fca3ec3f7
        # Removing self.ensure_one() will make few test cases to break of modules event_sale, sale_mrp and stock_dropshipping.
        # self.ensure_one()
        return float_round_custom(amount, precision_rounding=self.rounding)


class CurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    rate = fields.Float(
        digits=dp.get_precision("Currency Rate"), help="The rate of the currency to the currency of rate 1"
    )
