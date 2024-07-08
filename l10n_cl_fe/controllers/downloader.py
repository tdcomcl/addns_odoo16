from base64 import b64decode
from werkzeug.exceptions import InternalServerError
from odoo import http
from odoo.http import request


class Binary(http.Controller):
    def document(self, filename, filecontent):
        if not filecontent:
            return request.not_found()
        headers = [
            ("Content-Type", "application/xml"),
            ("Content-Disposition", content_disposition(filename)),
            ("charset", "utf-8"),
        ]
        return request.make_response(filecontent, headers=headers, cookies=None)

    @http.route(["/download/xml/invoice/<model('account.move'):document_id>"], type="http", auth="user")
    def download_document(self, document_id, **post):
        filename = ("%s.xml" % document_id.name).replace(" ", "_")
        filecontent = document_id.sii_xml_request.xml_envio
        return self.document(filename, filecontent)

    @http.route(["/download/xml/invoice_exchange/<model('account.move'):rec_id>"], type="http", auth="user")
    def download_document_exchange(self, rec_id, **post):
        filename = ("%s.xml" % rec_id.name).replace(" ", "_")
        att = rec_id._create_attachment()
        return self.document(filename, b64decode(att.datas))

    @http.route(["/download/xml/cf/<model('account.move.consumo_folios'):rec_id>"], type="http", auth="user")
    def download_cf(self, rec_id, **post):
        filename = ("CF_%s.xml" % rec_id.sii_xml_request.name).replace(" ", "_")
        filecontent = rec_id.sii_xml_request.xml_envio
        return self.document(filename, filecontent)

    @http.route(["/download/xml/libro/<model('account.move.book'):rec_id>"], type="http", auth="user")
    def download_book(self, rec_id, **post):
        filename = ("Libro_%s.xml" % rec_id.sii_xml_request.name).replace(" ", "_")
        filecontent = rec_id.sii_xml_request.xml_envio
        return self.document(filename, filecontent)
