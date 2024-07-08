import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountJournalSiiDocumentClass(models.Model):
    _name = "account.journal.sii_document_class"
    _description = "Journal SII Documents"
    _order = "sequence"

    @api.depends("sii_document_class_id", "sequence_id")
    def get_secuence_name(self):
        for r in self:
            sequence_name = r.sii_document_class_id.name or ""
            if r.sequence_id:
                sequence_name = "({}) {}".format(r.qty_available, r.sequence_id.name)
            r.name = sequence_name

    name = fields.Char(compute="get_secuence_name",)
    sii_document_class_id = fields.Many2one("sii.document_class", string="Document Type", required=True,)
    sequence_id = fields.Many2one(
        "ir.sequence",
        string="Entry Sequence",
        help="""This field contains the information related to the numbering \
            of the documents entries of this document type.""",
        domain=[('is_dte', '=', True)],
        check_company=True,
    )
    journal_id = fields.Many2one("account.journal", string="Journal", required=True,)
    sequence = fields.Integer(string="Sequence")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.user.company_id,)
    qty_available = fields.Integer(string="Quantity Available", related="sequence_id.qty_available")

    @api.onchange("sii_document_class_id")
    def check_sii_document_class(self):
        dc = self.sii_document_class_id
        if self.sequence_id and dc != self.sequence_id.sii_document_class_id:
            raise UserError("El tipo de Documento de la secuencia es distinto")
        if dc.es_guia():
            raise UserError("Las guías no es pueden agregar por esta área")

    @api.model
    def name_search(self, name, args=None, operator="ilike", limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(
                ["|", ("sequence_id.name", "=", name), ("sii_document_class_id.name", "=", name)] + args, limit=limit
            )
        if not recs:
            recs = self.search(
                ["|", ("sequence_id.name", operator, name), ("sii_document_class_id.name", operator, name)] + args,
                limit=limit,
            )
        return recs.name_get()
