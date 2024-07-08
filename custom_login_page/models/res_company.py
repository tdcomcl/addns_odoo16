# -*- coding: utf-8 -*-
################################################################################
#
#    Kolpolok Ltd. (https://www.kolpolok.com)
#    Author: Kolpolok (<https://www.kolpolok.com>)
#
################################################################################


from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    bg_image = fields.Binary(string="Image")
