# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _
from base64 import b64encode
import logging


_logger = logging.getLogger(__name__)
try:
    from facturacion_electronica import facturacion_electronica as fe
    from facturacion_electronica import clase_util as fe_util
except ImportError:
    _logger.warning("No se ha podido cargar fe")


class ProcessMailsDocument(models.Model):
    _name = "mail.message.dte.document"
    _description = "Pre Documento Recibido"
    _inherit = ["mail.thread"]

    def _get_dtes(self, xml):
        if xml.tag == "SetDTE":
            return xml.findall("DTE")
        envio = xml.find("SetDTE")
        if envio is None:
            if xml.tag == "DTE":
                return [xml]
            return []
        return envio.findall("DTE")

    def _get_xml(self):
        xml = self.dte_id._parse_xml(self.dte_xml)
        for dte in self._get_dtes(xml):
            Documento = dte.find("Documento")
            if Documento.get("ID") == self.id_dte:
                return fe_util.xml_to_string(dte)

    dte_id = fields.Many2one("mail.message.dte", string="DTE", readonly=True, ondelete="cascade",)
    new_partner = fields.Char(string="Proveedor Nuevo", readonly=True,)
    partner_id = fields.Many2one("res.partner", string="Proveedor",)
    date = fields.Date(string="Fecha Emsisión", readonly=True,)
    number = fields.Char(string="Folio", readonly=True,)
    document_class_id = fields.Many2one(
        "sii.document_class", string="Tipo de Documento", readonly=True,)
    amount = fields.Monetary(string="Monto", readonly=True,)
    monto_no_facturable = fields.Monetary(string="Monto no Facturable", readonly=True,)
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", readonly=True,
        default=lambda self: self.env.user.company_id.currency_id,
    )
    invoice_line_ids = fields.One2many("mail.message.dte.document.line", "document_id", string="Líneas del Documento",)
    global_descuentos_recargos = fields.One2many("mail.message.dte.document.gdr", "document_id", string="Líneas GDR",)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True,)
    state = fields.Selection(
        [("draft", "Recibido"), ("accepted", "Aceptado"), ("rejected", "Rechazado"),], default="draft",
    )
    move_id = fields.Many2one("account.move", string="Factura", readonly=True,)
    id_dte = fields.Char(string="ID DTE")
    dte_xml = fields.Binary(related="dte_id.xml_id.datas")
    xml = fields.Text(string="XML Documento")
    purchase_to_done = fields.Many2one(
        "purchase.order", string="Ordenes de Compra a validar", domain=[("state", "not in", ["accepted", "rejected"])],
    )
    claim = fields.Selection(
        [
            ("N/D", "No definido"),
            ("ACD", "Acepta Contenido del Documento"),
            ("RCD", "Reclamo al  Contenido del Documento "),
            ("ERM", " Otorga  Recibo  de  Mercaderías  o Servicios"),
            ("RFP", "Reclamo por Falta Parcial de Mercaderías"),
            ("RFT", "Reclamo por Falta Total de Mercaderías"),
            ("PAG", "DTE Pagado al Contado"),
            ("ENC", "Recepción de NC, distinta de anulación, que referencia al documento."),
            ("NCA", "Recepción de NC de anulación que referencia al documento."),
        ],
        string="Reclamo",
        copy=False,
        default="N/D",
    )
    claim_description = fields.Char(string="Detalle Reclamo",)
    claim_ids = fields.One2many("sii.dte.claim", "document_id", strign="Historial de Reclamos")
    sii_message = fields.Text(
        string="Respuesta SII"
    )
    journal_id = fields.Many2one('account.journal', string="Journal Destino")
    action = fields.Selection([
            ('create_po', 'Crear Orden de Compra'),
            ('create_move', 'Crear Factura'),
            ('both', 'Crear Ambas')
        ],
        string="Acción al aceptar",
        default='both',
        required=True
    )
    _order = "create_date DESC"

    @api.onchange('purchase_to_done')
    def auto_map_po_lines(self):
        if self._context.get('no_map_po_lines'):
            return
        if not self.purchase_to_done:
            for line in self.invoice_line_ids:
                line.purchase_line_id = False
            return
        lines = self.purchase_to_done.order_line
        tot_lines = len(lines)
        for line in self.invoice_line_ids:
            i = line.sequence
            if i <= tot_lines:
                line.purchase_line_id = lines[(i-1)]._origin.id
            else:
                line.purchase_line_id = False

    def _emisor(self, company_id):
        Emisor = {}
        Emisor["RUTEmisor"] = company_id.document_number
        Emisor["RznSoc"] = company_id.partner_id.name
        Emisor["GiroEmis"] = company_id.activity_description.name
        if company_id.phone:
            Emisor["Telefono"] = company_id.phone
        Emisor["CorreoEmisor"] = company_id.dte_email_id.name_get()[0][1]
        # Emisor['Actecos'] = self._actecos_emisor()
        Emisor["DirOrigen"] = company_id.street + " " + (company_id.street2 or "")
        if not company_id.city_id:
            raise UserError("Debe ingresar la Comuna de compañía emisora")
        Emisor["CmnaOrigen"] = company_id.city_id.name
        if not company_id.city:
            raise UserError("Debe ingresar la Ciudad de compañía emisora")
        Emisor["CiudadOrigen"] = company_id.city
        Emisor["Modo"] = "produccion" if company_id.dte_service_provider == "SII" else "certificacion"
        Emisor["NroResol"] = company_id.dte_resolution_number
        Emisor["FchResol"] = company_id.dte_resolution_date.strftime("%Y-%m-%d")
        return Emisor

    def _get_datos_empresa(self, company_id):
        signature_id = self.env.user.get_digital_signature(company_id)
        if not signature_id:
            raise UserError(
                _(
                    """There are not a Signature Cert Available for this user, please upload your signature or tell to someelse."""
                )
            )
        emisor = self._emisor(company_id)
        return {
            "Emisor": emisor,
            "firma_electronica": signature_id.parametros_firma(),
        }

    def _id_doc(self):
        IdDoc = {}
        IdDoc["TipoDTE"] = self.document_class_id.sii_code
        IdDoc["Folio"] = self.number
        IdDoc["FchEmis"] = self.date.strftime("%Y-%m-%d")
        return IdDoc

    def get_doc_rut(self):
        if self.new_partner:
            p = self.new_partner.split(' ')
            return p[0]
        commercial_partner_id = self.partner_id.commercial_partner_id or self.partner_id
        return commercial_partner_id.rut()

    def _receptor(self):
        Receptor = {'RUTRecep': self.get_doc_rut()}
        if self.new_partner:
            p = self.new_partner.split(' ')
            Receptor['RznSocRecep'] = ' '
            for s in p[1:]:
                Receptor['RznSocRecep'] += s
        else:
            commercial_partner_id = self.partner_id.commercial_partner_id or self.partner_id
            Receptor['RznSocRecep'] = commercial_partner_id.name
        return Receptor

    def _totales(self):
        return {"MntTotal": self.amount}

    def _encabezado(self,):
        Encabezado = {}
        Encabezado["IdDoc"] = self._id_doc()
        Encabezado["Receptor"] = self._receptor()
        Encabezado["Totales"] = self._totales()
        return Encabezado

    def _dte(self):
        if self.move_id:
            return self.move_id._dte()
        dte = {}
        dte["Encabezado"] = self._encabezado()
        return dte

    @api.onchange("move_id")
    def update_claim(self):
        for r in self.claim_ids:
            r.move_id = self.move_id.id

    @api.model
    def auto_accept_documents(self, limit=50):
        self.env.cr.execute(
            """
            select
                id
            from
                mail_message_dte_document
            where
                create_date + interval '8 days' < now()
                and
                state = 'draft'
            limit {}
            """.format(
                limit
            )
        )
        self.browse([line.get("id") for line in self.env.cr.dictfetchall()]).accept_document()

    def _process_document(self):
        xml = self.xml
        filename = self.dte_id.name
        if self.dte_xml:
            xml = self._get_xml()
        vals = {
            "xml_file": b64encode(xml.encode("ISO-8859-1")),
            "filename": filename,
            "pre_process": False,
            "document_id": self.id,
            "option": "accept",
            "action": self.action,
        }
        val = self.env["sii.dte.upload_xml.wizard"].sudo().create(vals)
        return val.confirm(ret=True)

    def process_document(self):
        if self.action in ["both", "create_po"] and not any(aml.purchase_line_id or aml.create_pol for aml in self.invoice_line_ids):
            raise UserError("Debe marcar almenos una línea de pedido para crear")
        self._process_document()

    def accept_document(self):
        created = []
        for r in self:
            try:
                r.get_dte_claim()
            except Exception as e:
                _logger.warning("Problema al obtener claim desde accept %s" % str(e), exc_info=True)
            if r.move_id and r.state != "draft":
                continue
            if r.move_id:
                resp = r.move_id.ids
            else:
                resp = r._process_document()
            created.extend(resp)
            if r.company_id.dte_service_provider == "SIICERT":
                r.state = "accepted"
                continue
            for i in self.env["account.move"].browse(resp):
                if i.claim in ["ACD", "ERM", "PAG"]:
                    r.state = "accepted"
        action = {
            'name': _('Accepted Moves'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
        }
        if created:
            action['domain'] = [('id', 'in', created)]
        return action

    def reject_document(self):
        for r in self:
            if r.xml:
                vals = {
                    "document_ids": [(6, 0, r.ids)],
                    "estado_dte": "2",
                    "action": "validate",
                    "claim": "RCD",
                }
                val = self.env["sii.dte.validar.wizard"].sudo().create(vals)
                val.confirm()
            if r.claim in ["RCD"]:
                r.state = "rejected"

    def set_dte_claim(self, claim):
        if self.document_class_id.sii_code not in [33, 34, 43]:
            self.claim = claim
            return
        folio = self.number
        tipo_dte = self.document_class_id.sii_code
        datos = self._get_datos_empresa(self.company_id)
        rut_emisor = self.get_doc_rut()
        datos["DTEClaim"] = [
            {
                "RUTEmisor": rut_emisor,
                "TipoDTE": tipo_dte,
                "Folio": folio,
                "Claim": claim
            }
        ]
        key = "RUT%sT%sF%s" % (rut_emisor, tipo_dte, folio)
        try:
            respuesta = fe.ingreso_reclamo_documento(datos)[key]
        except Exception as e:
            msg = "Error al ingresar Reclamo DTE"
            _logger.warning("{}: {}".format(msg, str(e)), exc_info=True)
            if e.args[0][0] == 503:
                raise UserError(
                    "%s: Conexión al SII caída/rechazada o el SII está temporalmente fuera de línea, reintente la acción"
                    % (msg)
                )
            raise UserError("{}: {}".format(msg, str(e)))
        self.claim_description = respuesta
        if respuesta.get(key,
                         {'respuesta': {'codResp': 9}})['respuesta']["codResp"] in [0, 7]:
            self.claim = claim

    def get_dte_claim(self):
        folio = self.number
        tipo_dte = self.document_class_id.sii_code
        datos = self._get_datos_empresa(self.company_id)
        rut_emisor = self.get_doc_rut()
        datos["DTEClaim"] = [
            {
                "RUTEmisor": rut_emisor,
                "TipoDTE": tipo_dte,
                "Folio": folio,
            }
        ]
        try:
            key = "RUT%sT%sF%s" % (rut_emisor, tipo_dte, folio)
            respuesta = fe.consulta_reclamo_documento(datos)[key]
            self.claim_description = respuesta
            if respuesta.get(key,
                             {'respuesta': {'codResp': 9}})['respuesta']["codResp"] in [15]:
                for res in respuesta.listaEventosDoc:
                    if self.claim != "ACD":
                        if self.claim != "ERM":
                            self.claim = res.codEvento
            date_end = self.create_date + relativedelta(days=8)
            if self.claim in ["ACD", "ERM", "PAG"]:
                self.state = "accepted"
            elif date_end <= datetime.now() and self.claim == "N/D":
                self.state = "accepted"
        except Exception as e:
            _logger.warning("Error al obtener aceptación %s" % (str(e)), exc_info=True)
            if self.company_id.dte_service_provider == "SII":
                raise UserError("Error al obtener aceptación: %s" % str(e))

    def get_claim(self):
        date_end = self.create_date + relativedelta(days=8)
        if date_end <= datetime.now() and self.claim == "N/D":
            return self.accept_document()
        self.get_dte_claim()


class ProcessMailsDocumentLines(models.Model):
    _name = "mail.message.dte.document.line"
    _description = "Pre Document Line"
    _order = "sequence, id"

    name = fields.Char(string="Nombre en xml")
    document_id = fields.Many2one("mail.message.dte.document", string="Documento", ondelete="cascade",)
    sequence = fields.Integer(string="Número de línea", default=1, readonly=True)
    product_id = fields.Many2one("product.product", string="Producto",)
    new_product = fields.Char(string="Nuevo Producto", readonly=True,)
    description = fields.Char(string="Descripción", readonly=True,)
    product_description = fields.Char(string="Descripción Producto", readonly=True,)
    quantity = fields.Float(string="Cantidad", readonly=True,)
    price_unit = fields.Monetary(string="Precio Unitario", readonly=True,)
    discount = fields.Float(string='Discount (%)', readonly=True, digits='Discount', default=0.0,)
    price_subtotal = fields.Monetary(string="Total", readonly=True,)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', readonly=True)
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", readonly=True, default=lambda self: self.env.user.company_id.currency_id,
    )
    ind_exe = fields.Selection([
            ('1', 'No afecto o exento de IVA (10)'),
            ('2', 'Producto o servicio no es facturable'),
            ('3', 'Garantía de depósito por envases (Cervezas, Jugos, Aguas Minerales, Bebidas Analcohólicas u otros autorizados por Resolución especial)'),
            ('4', 'Ítem No Venta. (Para facturas y guías de despacho (ésta última con Indicador Tipo de Traslado de Bienes igual a 1) y este ítem no será facturado.'),
            ('5', 'Ítem a rebajar. Para guías de despacho NO VENTA que rebajan guía anterior. En el área de referencias se debe indicar la guía anterior.'),
            ('6', 'Producto o servicio no facturable negativo (excepto en liquidaciones-factura)'),
        ],
        string="Indicador Exento"
    )
    company_id = fields.Many2one(
        related='document_id.company_id', store=True, readonly=True, precompute=True,
        index=True,
    )
    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        readonly=True,
        context={'active_test': False},
        check_company=True,
    )
    purchase_line_id = fields.Many2one('purchase.order.line', string="Línea de Orden de Compra")
    create_pol = fields.Boolean(
        string="Crear Línea Orden de Compra",
    )
    create_move_line = fields.Boolean(
        string="Crear Línea de Movimiento",
    )

    @api.onchange('purchase_line_id')
    def _onchange_purchase_line_id(self):
        if self.purchase_line_id:
            self.product_id = self.purchase_line_id.product_id

class MMDTEDGlobalDescuentoRecargo(models.Model):
    _name = "mail.message.dte.document.gdr"
    _description = "Linea de descuento global dte document"

    def _get_name(self):
        for g in self:
            type = "Descuento"
            if g.type == "R":
                type = "Recargo"
            calculo = "Porcentaje"
            if g.gdr_type == "amount":
                calculo = "Monto"
            g.name = type + "-" + calculo + ": " + (g.gdr_detail or "")

    name = fields.Char(compute="_get_name", string="Name")
    type = fields.Selection(
        [("D", "Descuento"), ("R", "Recargo"),],
        string="Seleccione Descuento/Recargo Global",
        default="D",
        required=True,
    )
    valor = fields.Float(
        string="Descuento/Recargo Global", default=0.00, required=True, digits="Global DR"
    )
    gdr_type = fields.Selection(
        [("amount", "Monto"), ("percent", "Porcentaje"),], string="Tipo de descuento", default="percent", required=True,
    )
    gdr_detail = fields.Char(string="Razón del descuento")
    amount_untaxed_global_dr = fields.Float(string="Descuento/Recargo Global", default=0.00)
    aplicacion = fields.Selection([("flete", "Flete"), ("seguro", "Seguro"),], string="Aplicación del Desc/Rec",)
    impuesto = fields.Selection(
        [("afectos", "Solo Afectos"), ("exentos", "Solo Exentos"), ("no_facturables", "Solo No Facturables")],
        default="afectos",
    )
    document_id = fields.Many2one("mail.message.dte.document", string="DTE", copy=False,)
    account_id = fields.Many2one('account.account', string='Account',
        company_dependent=True,
        domain="[('deprecated', '=', False), ('company_id', '=', current_company_id)]",
        #default=lambda self: self.move_id.journal_id.default_gd_account_id if self.type == 'D' else self.move_id.journal_id.default_gr_account_id
    )
