from odoo import fields, models


class SIIDocumentClass(models.Model):
    _name = "sii.document_class"
    _description = "SII Document Class"

    name = fields.Char("Name", size=120)
    doc_code_prefix = fields.Char(
        "Document Code Prefix",
        help="Prefix for Documents Codes on Invoices \
        and Account Moves. For eg. 'FAC' will build 'FAC 00001' Document Number",
    )
    code_template = fields.Char("Code Template for Journal")
    sii_code = fields.Integer("SII Code", required=True)
    document_letter_id = fields.Many2one("sii.document_letter", "Document Letter")
    report_name = fields.Char("Name on Reports", help='Name that will be printed in reports, for example "CREDIT NOTE"')
    document_type = fields.Selection(
        [
            ("invoice", "Invoices"),
            ("invoice_in", "Purchase Invoices"),
            ("debit_note", "Debit Notes"),
            ("credit_note", "Credit Notes"),
            ("stock_picking", "Stock Picking"),
            ("other_document", "Other Documents"),
        ],
        string="Document Type",
        help="It defines some behaviours on automatic journal selection and\
        in menus where it is shown.",
    )
    active = fields.Boolean("Active", default=True)
    dte = fields.Boolean("DTE", required=True)
    use_prefix = fields.Boolean(string="Usar Prefix en las referencias DTE", default=False,)

    def es_boleta_afecta(self):
        return self.sii_code in [35, 39, 70, 71]

    def es_boleta_exenta(self):
        return self.sii_code in [38, 41]

    def es_boleta(self):
        return self.es_boleta_afecta() or self.es_boleta_exenta()

    def es_nc_exportacion(self):
        return self.sii_code in [112]

    def es_nd_exportacion(self):
        return self.sii_code in [111]

    def es_factura_afecta(self):
        return self.sii_code in [30, 33]

    def es_factura_exenta(self):
        return self.sii_code in [32, 34]

    def es_factura(self):
        return self.es_factura_afecta() or self.es_factura_exenta()

    def es_factura_exportacion(self):
        return self.sii_code in [110]

    def es_factura_compra(self):
        return self.sii_code in [45, 46]

    def es_liquidacion(self):
        return self.sii_code in [43]

    def es_guia(self):
        return self.sii_code in [50, 52]

    def es_nc(self):
        return self.sii_code in [60, 61] or self.es_nc_exportacion()

    def es_nd(self):
        return self.sii_code in [55, 56] or self.es_nd_exportacion()

    def es_exportacion(self):
        return self.es_factura_exportacion() or self.es_nc_exportacion() or self.es_nd_exportacion()
