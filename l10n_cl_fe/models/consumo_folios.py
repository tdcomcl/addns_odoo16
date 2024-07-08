import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)
try:
    from facturacion_electronica import facturacion_electronica as fe
    from facturacion_electronica.consumo_folios import ConsumoFolios as CF
except Exception as e:
    _logger.warning("Problema al cargar Facturación electrónica: %s" % str(e))


class ConsumoFolios(models.Model):
    _name = "account.move.consumo_folios"
    _description = "Consumo Diario de Folios"
    order = "fecha_inicio desc"

    sii_xml_request = fields.Many2one(
        "sii.xml.envio", string="SII XML Request", copy=False, readonly=True, states={"draft": [("readonly", False)]},
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("NoEnviado", "No Enviado"),
            ("EnCola", "En Cola"),
            ("Enviado", "Enviado"),
            ('EnProceso', 'EnProceso'),
            ("Aceptado", "Aceptado"),
            ("Rechazado", "Rechazado"),
            ("Reparo", "Reparo"),
            ("Proceso", "Procesado"),
            ("Reenviar", "Reenviar"),
            ("Anulado", "Anulado"),
        ],
        string="Resultado",
        index=True,
        readonly=True,
        default="draft",
        track_visibility="onchange",
        copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Invoice.\n"
        " * The 'Pro-forma' status is used the invoice does not have an invoice number.\n"
        " * The 'Open' status is used when user create invoice, an invoice number is generated. Its in open status till user does not pay invoice.\n"
        " * The 'Paid' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled.\n"
        " * The 'Cancelled' status is used when user cancel invoice.",
    )
    move_ids = fields.Many2many("account.move", readonly=True, states={"draft": [("readonly", False)]},)
    fecha_inicio = fields.Date(
        string="Fecha Inicio",
        readonly=True,
        states={"draft": [("readonly", False)]},
        default=lambda self: fields.Date.context_today(self),
    )
    fecha_final = fields.Date(
        string="Fecha Final",
        readonly=True,
        states={"draft": [("readonly", False)]},
        default=lambda self: fields.Date.context_today(self),
    )
    correlativo = fields.Integer(
        string="Correlativo", readonly=True, states={"draft": [("readonly", False)]}, invisible=True,
    )
    sec_envio = fields.Integer(string="Secuencia de Envío", readonly=True, states={"draft": [("readonly", False)]},)
    total_neto = fields.Monetary(string="Total Neto", store=True, readonly=False, compute="get_totales",)
    total_iva = fields.Monetary(string="Total Iva", store=True, readonly=False, compute="get_totales",)
    total_exento = fields.Monetary(string="Total Exento", store=True, readonly=False, compute="get_totales",)
    total = fields.Monetary(string="Monto Total", store=True, readonly=False, compute="get_totales",)
    total_boletas = fields.Integer(string="Total Boletas", store=True, readonly=False, compute="get_totales",)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.user.company_id.id,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    name = fields.Char(string="Detalle", required=True, readonly=True, states={"draft": [("readonly", False)]},)
    date = fields.Date(
        string="Date",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        default=lambda self: fields.Date.context_today(self),
    )
    detalles = fields.One2many(
        "account.move.consumo_folios.detalles",
        "cf_id",
        string="Detalle Rangos",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    impuestos = fields.One2many(
        "account.move.consumo_folios.impuestos",
        "cf_id",
        string="Detalle Impuestos",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    anulaciones = fields.One2many(
        "account.move.consumo_folios.anulaciones",
        "cf_id",
        string="Detalle Impuestos",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.user.company_id.currency_id,
        required=True,
        track_visibility="always",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    responsable_envio = fields.Many2one("res.users",)
    sii_result = fields.Selection(
        [
            ("draft", "Borrador"),
            ("NoEnviado", "No Enviado"),
            ("Enviado", "Enviado"),
            ('EnProceso', 'EnProceso'),
            ("Aceptado", "Aceptado"),
            ("Rechazado", "Rechazado"),
            ("Reparo", "Reparo"),
            ("Proceso", "Proceso"),
            ("Reenviar", "Reenviar"),
            ("Anulado", "Anulado"),
        ],
        related="state",
    )

    _order = "fecha_inicio desc"

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = super(ConsumoFolios, self).read_group(
            domain, fields, groupby, offset, limit=limit, orderby=orderby, lazy=lazy
        )
        if "total_iva" in fields:
            for line in res:
                if "__domain" in line:
                    lines = self.search(line["__domain"])
                    line.update(
                        {"total_neto": 0, "total_iva": 0, "total_exento": 0, "total": 0, "total_boletas": 0,}
                    )
                    for l in lines:
                        line.update(
                            {
                                "total_neto": line["total_neto"] + l.total_neto,
                                "total_iva": line["total_iva"] + l.total_iva,
                                "total_exento": line["total_exento"] + l.total_exento,
                                "total": line["total"] + l.total,
                                "total_boletas": line["total_boletas"] + l.total_boletas,
                            }
                        )
        return res

    @api.onchange("impuestos")
    @api.depends("impuestos")
    def get_totales(self):
        for r in self:
            total_iva = 0
            total_exento = 0
            total = 0
            total_boletas = 0
            for d in r.impuestos.filtered(lambda a: a.tpo_doc.sii_code in [39, 41]):
                total_iva += d.monto_iva
                total_exento += d.monto_exento
                total += d.monto_total
            for d in r.detalles:
                if d.tpo_doc.sii_code in [39, 41] and d.tipo_operacion == "utilizados":
                    total_boletas += d.cantidad
            r.total_neto = total - total_iva - total_exento
            r.total_iva = total_iva
            r.total_exento = total_exento
            r.total = total
            r.total_boletas = total_boletas

    def _get_moves(self):
        recs = []
        for m in self.with_context(lang="es_CL").move_ids.filtered(
            lambda a: a.is_invoice() and (a.es_boleta() or a.es_nc_boleta())\
                and a.sii_document_number not in [0, False]):
            recs.append(m)
        return recs

    def _get_datos(self):
        grupos = {}
        recs = self._get_moves()
        for r in recs:
            grupos.setdefault(r.document_class_id.sii_code, [])
            grupos[r.document_class_id.sii_code].append(r.with_context(tax_detail=True)._dte())
        for r in self.anulaciones:
            grupos.setdefault(r.tpo_doc.sii_code, [])
            for i in range(r.rango_inicio, r.rango_final + 1):
                grupos[r.tpo_doc.sii_code].append(
                    {
                        "Encabezado": {
                            "IdDoc": {"Folio": i, "FechaEmis": self.fecha_inicio.strftime("%d-%m-%Y"), "Anulado": True,}
                        }
                    }
                )
        datos = {
            "resumen": False,
            "FchInicio": self.fecha_inicio.strftime("%d-%m-%Y"),
            "FchFinal": self.fecha_final.strftime("%d-%m-%Y"),
            "SecEnvio": self.sec_envio,
            "Correlativo": self.correlativo,
            "Documento": [{"TipoDTE": k, "documentos": v} for k, v in grupos.items()],
        }
        return datos

    def _get_resumenes(self):
        datos = self._get_datos()
        resumenes = CF(datos)._get_resumenes()
        return resumenes

    @api.onchange("move_ids", "anulaciones")
    def _resumenes(self):
        resumenes = self._get_resumenes()
        self.write({
            'detalles' : [(5, 0, 0)],
            'impuestos' : [(5, 0, 0)],
        })
        detalles = []
        def pushItem(key_item, item, tpo_doc):
            rango = {
                "tipo_operacion": "utilizados" if key_item == "RangoUtilizados" else "anulados",
                "folio_inicio": item["Inicial"],
                "folio_final": item["Final"],
                "cantidad": int(item["Final"]) - int(item["Inicial"]) + 1,
                "tpo_doc": self.env["sii.document_class"].search([("sii_code", "=", tpo_doc)]).id,
            }
            detalles.append([0, 0, rango])

        for r, value in resumenes.items():
            if value.get("T%s" % str(r)):
                Rangos = value["T" + str(r)]
                if "itemUtilizados" in Rangos:
                    for rango in Rangos["itemUtilizados"]:
                        pushItem("RangoUtilizados", rango, r)
                if "itemAnulados" in Rangos:
                    for rango in Rangos["itemAnulados"]:
                        pushItem("RangoAnulados", rango, r)
        docs = {}
        for r, value in resumenes.items():
            if value.get("FoliosUtilizados", False):
                docs[r] = {
                    "tpo_doc": self.env["sii.document_class"].search([("sii_code", "=", r)]).id,
                    "cantidad": value["FoliosUtilizados"],
                    "monto_neto": value["MntNeto"],
                    "monto_iva": value["MntIva"],
                    "monto_exento": value["MntExento"],
                    "monto_total": value["MntTotal"],
                }
        impuestos = []
        for _key, i in docs.items():
            i["currency_id"] = self.env.user.company_id.currency_id.id
            impuestos.append([0, 0, i])
        self.write({
            'detalles' : detalles,
            'impuestos' : impuestos,
        })

    @api.onchange("fecha_inicio", "company_id", "fecha_final")
    def set_data(self):
        self.move_ids = False
        if self.fecha_inicio > fields.Date.context_today(self):
            raise UserError("No puede hacer Consumo de Folios de días futuros")
        self.name = self.fecha_inicio
        self.fecha_final = self.fecha_inicio
        self.move_ids = self.env["account.move"].search(
                [
                    ("document_class_id.sii_code", "in", [39, 41, 61]),
                    ("invoice_date", "=", self.fecha_inicio),
                    ("company_id", "=", self.company_id.id),
                    ("sii_document_number", 'not in', [0, False]),
                ]
            ).filtered(lambda a: a.is_invoice() and (a.es_boleta() or a.es_nc_boleta()))
        consumo = self.search(
            [
                ("fecha_inicio", "=", self.fecha_inicio),
                ("state", "not in", ["draft", "Rechazado"]),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
            order="sec_envio DESC"
        )
        if consumo:
            self.sec_envio = consumo.sec_envio + 1

    def copy(self, default=None):
        res = super(ConsumoFolios, self).copy(default)
        res.set_data()
        return res

    def unlink(self):
        for libro in self:
            if libro.state not in ("draft", "cancel"):
                raise UserError(_("You cannot delete a Validated book."))
        return super(ConsumoFolios, self).unlink()

    def get_xml_file(self):
        return {
            "type": "ir.actions.act_url",
            "url": "/download/xml/cf/%s" % (self.id),
            "target": "self",
        }

    def validar_consumo_folios(self):
        self._validar()
        consumos = self.search(
            [
                ("fecha_inicio", "=", self.fecha_inicio),
                ("state", "not in", ["draft", "Rechazado", "Anulado"]),
                ("company_id", "=", self.company_id.id),
                ("id", "!=", self.id),
            ]
        )
        for r in consumos:
            r.state = "Anulado"
        return self.write({"state": "NoEnviado"})

    def _emisor(self):
        Emisor = {}
        Emisor["RUTEmisor"] = self.company_id.partner_id.rut()
        Emisor["RznSoc"] = self.company_id.name
        Emisor["Modo"] = "produccion" if self.company_id.dte_service_provider == "SII" else "certificacion"
        Emisor["NroResol"] = self.company_id.dte_resolution_number
        Emisor["FchResol"] = self.company_id.dte_resolution_date.strftime("%Y-%m-%d")
        Emisor["ValorIva"] = 19
        return Emisor

    def _get_datos_empresa(self):
        signature_id = self.env.user.get_digital_signature(self.company_id)
        if not signature_id:
            raise UserError(
                _(
                    """There are not a Signature Cert Available for this user, please upload your signature or tell to someelse."""
                )
            )
        emisor = self._emisor()
        return {
            "Emisor": emisor,
            "firma_electronica": signature_id.parametros_firma(),
        }

    def _validar(self):
        if not self.impuestos:
            self._resumenes()
        datos = self._get_datos_empresa()
        datos["ConsumoFolios"] = [self._get_datos()]
        datos["test"] = True
        result = fe.consumo_folios(datos)[0]
        envio_dte = result["sii_xml_request"]
        doc_id = "{}_{}".format(self.fecha_inicio, self.sec_envio)
        self.sii_xml_request = (
            self.env["sii.xml.envio"]
            .create({"xml_envio": envio_dte, "name": doc_id, "company_id": self.company_id.id,})
            .id
        )

    def do_dte_send_consumo_folios(self):
        if self.state not in ["draft", "NoEnviado", "Rechazado"]:
            raise UserError("El Consumo de Folios ya ha sido enviado")
        if not self.sii_xml_request or self.sii_xml_request.state == "Rechazado":
            if self.sii_xml_request:
                self.sii_xml_request.unlink()
            self._validar()
        self.env["sii.cola_envio"].create(
            {
                "company_id": self.company_id.id,
                "doc_ids": [self.id],
                "model": "account.move.consumo_folios",
                "user_id": self.env.user.id,
                "tipo_trabajo": "envio",
            }
        )
        self.state = "EnCola"

    def do_dte_send(self, n_atencion=""):
        if not self.sii_xml_request:
            self._validar()
        if self.sii_xml_request and self.sii_xml_request.state == "Rechazado":
            self.sii_xml_request.unlink()
            self._validar()
            self.sii_xml_request.state = "NoEnviado"
        if self.state in ["NoEnviado", "EnCola"]:
            self.sii_xml_request.send_xml()
        return self.sii_xml_request

    def _get_send_status(self):
        self.sii_xml_request.get_send_status()
        if self.sii_xml_request.state == "Aceptado":
            self.state = "Proceso"
        else:
            self.state = self.sii_xml_request.state


    def ask_for_dte_status(self):
        self._get_send_status()

    def get_sii_result(self):
        for r in self:
            if r.sii_xml_request.state == "NoEnviado":
                r.state = "EnCola"
                continue
            r.state = r.sii_xml_request.state


class DetalleCOnsumoFolios(models.Model):
    _name = "account.move.consumo_folios.detalles"
    _description = "Línea detalle Consumo de folios"

    cf_id = fields.Many2one("account.move.consumo_folios", string="Consumo de Folios", ondelete="cascade",)
    tpo_doc = fields.Many2one("sii.document_class", string="Tipo de Documento")
    tipo_operacion = fields.Selection([("utilizados", "Utilizados"), ("anulados", "Anulados")])
    folio_inicio = fields.Integer(string="Folio Inicio")
    folio_final = fields.Integer(string="Folio Final")
    cantidad = fields.Integer(string="Cantidad Emitidos")


class DetalleImpuestos(models.Model):
    _name = "account.move.consumo_folios.impuestos"
    _description = "Línea Impuestos Consumo de folios"

    cf_id = fields.Many2one("account.move.consumo_folios", string="Consumo de Folios", ondelete="cascade",)
    tpo_doc = fields.Many2one("sii.document_class", string="Tipo de Documento")
    impuesto = fields.Many2one("account.tax")
    cantidad = fields.Integer(string="Cantidad")
    monto_neto = fields.Monetary(string="Monto Neto")
    monto_iva = fields.Monetary(string="Monto IVA",)
    monto_exento = fields.Monetary(string="Monto Exento",)
    monto_total = fields.Monetary(string="Monto Total",)
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        default=lambda self: self.env.user.company_id.currency_id,
        required=True,
        track_visibility="always",
    )


class Anulaciones(models.Model):
    _name = "account.move.consumo_folios.anulaciones"
    _description = "Línea anulación de folios para Consumo de folios"

    cf_id = fields.Many2one("account.move.consumo_folios", string="Consumo de Folios", ondelete="cascade",)
    tpo_doc = fields.Many2one(
        "sii.document_class", string="Tipo de documento", required=True, domain=[("sii_code", "in", [39, 41, 61])],
    )
    rango_inicio = fields.Integer(required=True, string="Rango Inicio")
    rango_final = fields.Integer(required=True, string="Rango Final")
