from odoo import api, fields, models


class PartnerActivities(models.Model):
    _name = "partner.activities"
    _description = "SII Economical Activities"


    def name_get(self):
        res = []
        for r in self:
            res.append((r.id, (r.code and "[" + r.code + "] " + r.name or "")))
        return res

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(["|", ("name", "=", name), ("code", "=", name)] + args, limit=limit)
        if not recs:
            recs = self.search(["|", ("name", operator, name), ("code", operator, name)] + args, limit=limit)
        return recs.name_get()

    code = fields.Char(string="Activity Code", required=True,)
    parent_id = fields.Many2one("partner.activities", string="Parent Activity", ondelete="cascade",)
    name = fields.Char(string="Nombre Completo", required=True, translate=True,)
    vat_affected = fields.Selection(
        (("SI", "Si"), ("NO", "No"), ("ND", "ND"),), string="VAT Affected", required=True, default="SI",
    )
    tax_category = fields.Selection(
        (("1", "1"), ("2", "2"), ("ND", "ND"),), string="TAX Category", required=True, default="1",
    )
    internet_available = fields.Boolean(string="Available at Internet", default=True,)
    active = fields.Boolean(string="Active", help="Allows you to hide the activity without removing it.", default=True,)
