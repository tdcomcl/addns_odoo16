import json
import logging
import re
from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)
try:
    import urllib3

    urllib3.disable_warnings()
    pool = urllib3.PoolManager()
except ImportError:
    _logger.warning("no se ha cargado urllib3")


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _get_default_tp_type(self):
        try:
            return self.env.ref("l10n_cl_fe.res_IVARI")
        except Exception as ex:
            _logger.error(tools.ustr(ex))
            return self.env["sii.responsability"]

    def _get_default_doc_type(self):
        try:
            return self.env.ref("l10n_cl_fe.dt_RUT")
        except Exception as ex:
            _logger.error(tools.ustr(ex))
            return self.env["sii.document_type"]

    @api.model
    def _get_default_country(self):
        return self.env.user.company_id.country_id.id or self.env.user.partner_id.country_id.id

    @api.depends("child_ids")
    def _compute_dte_email(self):
        for p in self:
            p.dte_email_id = self.env['res.partner']
            if p.dte_email == p.email:
                continue
            for dte in p.child_ids:
                if dte.type == "dte" and dte.principal:
                    p.dte_email_id = dte.id
                    p.dte_email = dte.email
                    break


    type = fields.Selection(selection_add=[("dte", "Contacto DTE"),])
    state_id = fields.Many2one("res.country.state", "Región",)
    responsability_id = fields.Many2one(
        "sii.responsability", string="Responsability", default=lambda self: self._get_default_tp_type(),
    )
    document_type_id = fields.Many2one(
        "sii.document_type", string="Document type", default=lambda self: self._get_default_doc_type(),
    )
    document_number = fields.Char(string="Document number", size=64,)
    start_date = fields.Date(string="Start-up Date",)
    tp_sii_code = fields.Char("Tax Payer SII Code", compute="_get_tp_sii_code", readonly=True,)
    activity_description = fields.Many2one("sii.activity.description", string="Glosa Giro", ondelete="restrict",)
    dte_email_id = fields.Many2one("res.partner", string="DTE Email Principal", compute="_compute_dte_email",)
    dte_email = fields.Char(
        string="DTE Email",
        # related='dte_email_id.name',
    )
    principal = fields.Boolean(string="Principal DTE", default=lambda self: self._verify_principal(),)
    send_dte = fields.Boolean(string="Auto Enviar DTE",)
    acteco_ids = fields.Many2many("partner.activities", string="Activities Names",)
    sync = fields.Boolean(string="syncred", default=False,)
    last_sync_update = fields.Datetime(string="Fecha Actualizado",)
    es_mipyme = fields.Boolean(string="Es MiPyme", help="Usa el sistema gratuito del SII")

    def rut(self):
        rut = "66666666-6"
        if self.document_number:
            d = self.document_number.replace(".", "").split("-")
            rut = str(int(d[0])) + "-" + d[1]
        return rut

    def write(self, vals):
        result = super(ResPartner, self).write(vals)
        if not vals.get("sync", False):
            for k in vals.keys():
                if k in ("name", "dte_email", "street", "email", "acteco_ids", "website"):
                    try:
                        for r in self:
                            if (
                                r.sync
                                and r.document_number
                                and not r.parent_id
                                and self.check_vat_cl(r.document_number.replace(".", "").replace("-", ""))
                            ):
                                company = r.company_id or self.env.company
                                url = company.url_remote_partners
                                token = company.token_remote_partners
                                if not url or not token or not company.sync_remote_partners:
                                    continue
                                data = {
                                    "token": token,
                                    "version": 2.0,
                                    "origen": self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
                                }
                                data.update(r.get_data_to_put())
                                r.put_remote_user_data(url, data)
                    except Exception as e:
                        _logger.warning("Error en subida información %s" % str(e), exc_info=True)
                    break
        return result

    @api.onchange("dte_email")
    def set_temporal_email_cambiar_a_related(self):
        """ Esto eliminar en la versión siguiente, es solamente para evitar
            problemas al actualizar """
        if not self.is_company and not self.dte_email or (not self.email and not self.dte_email):
            if self.dte_email_id:
                self.dte_email_id.unlink()
            return
        if self.dte_email == self.email:
            self.send_dte = True
            self.principal = True
            return
        if not self.dte_email_id:
            partners = []
            for rec in self.child_ids:
                partners.append((4, rec.id, False))
            partners.append(
                (
                    0,
                    0,
                    {
                        "type": "dte",
                        "name": self.dte_email,
                        "email": self.dte_email,
                        "send_dte": True,
                        "principal": True,
                    },
                )
            )
            self.child_ids = partners
        elif self.dte_email_id and self.dte_email_id.email != self.dte_email:
            __name = self.dte_email_id.name
            if __name == self.dte_email_id.email:
                __name = self.dte_email
            self.dte_email_id.name = __name
            self.dte_email_id.email = self.dte_email
        else:
            for r in self.child_ids:
                if r.type == "dte":
                    r.email = self.dte_email
                    r.name = self.dte_email

    @api.onchange("principal")
    def verify_principal(self):
        self._verify_principal()

    def _verify_principal(self):
        another = False
        if self.type != "dte":
            return another
        check_id = self.id
        if self.parent_id:
            check_id = self.parent_id.id
        another = self.env["res.partner"].search([("parent_id", "=", check_id), ("principal", "=", True)])
        if another:
            raise UserError(_("Existe otro correo establecido como Principal"))
        return True

    # def create(self, vals):
    #    partner = super(ResPartner, self).create(vals)
    #    if vals.get('dte_email'):
    #        dte_email_id = self.env['res.partner'].create(
    #                              {
    #                                  'parent_id': self.id,
    #                                  'type': 'dte',
    #                                  'name': self.dte_email,
    #                                  'email': self.dte_email,
    #                                  'send_dte': True,
    #                                  'principal': True,
    #                              })
    #        self.dte_email_id = dte_email_id.id


    @api.onchange("responsability_id")
    def _get_tp_sii_code(self):
        for record in self:
            record.tp_sii_code = str(record.responsability_id.tp_sii_code)

    @api.onchange("document_number", "document_type_id")
    def onchange_document(self):
        if self.document_number and (self.document_type_id == self.env.ref("l10n_cl_fe.dt_RUT")
            or self.document_type_id == self.env.ref("l10n_cl_fe.dt_RUN")):
            document_number = (re.sub("[^1234567890Kk]", "", str(self.document_number))).zfill(9).upper()
            if not self.check_vat_cl(document_number):
                return {"warning": {"title": _("Rut Erróneo"), "message": _("Rut Erróneo"),}}
            vat = "CL%s" % document_number
            exist = self.env["res.partner"].search(
                [
                    ("vat", "=", vat),
                    ("vat", "!=", "CL555555555"),
                    ("commercial_partner_id", "!=", self.commercial_partner_id.id),
                ],
                limit=1,
            )
            if exist:
                self.vat = ""
                self.document_number = ""
                return {
                    "warning": {
                        "title": "Informacion para el Usuario",
                        "message": _("El usuario %s está utilizando este documento") % exist.name,
                    }
                }
            self.vat = vat
            self.document_number = "{}.{}.{}-{}".format(
                document_number[0:2], document_number[2:5], document_number[5:8], document_number[-1],
            )
        elif self.document_number and self.document_type_id == self.env.ref("l10n_cl_fe.dt_Sigd"):
            self.document_number = ""
        else:
            self.vat = ""
        self.fill_partner()

    @api.onchange("city_id")
    def _onchange_city_id(self):
        if self.city_id:
            self.country_id = self.city_id.state_id.country_id.id
            self.state_id = self.city_id.state_id.id
            self.city = self.city_id.name

    @api.constrains("vat", "commercial_partner_id")
    def _rut_unique(self):
        for r in self.sudo():
            if not r.vat or r.parent_id:
                continue
            partner = self.env["res.partner"].sudo().search(
                [("vat", "=", r.vat), ("id", "!=", r.id), ("commercial_partner_id", "!=", r.commercial_partner_id.id),]
            )
            if r.vat != "CL555555555" and partner:
                raise UserError(_("El rut: %s debe ser único") % r.vat)
                return False

    def check_vat_cl(self, vat):
        body, vdig = "", ""
        if len(vat) != 9:
            return False
        else:
            body, vdig = vat[:-1], vat[-1].upper()
        try:
            vali = list(range(2, 8)) + [2, 3]
            operar = "0123456789K0"[11 - (sum([int(digit) * factor for digit, factor in zip(body[::-1], vali)]) % 11)]
            if operar == vdig:
                return True
            else:
                return False
        except IndexError:
            return False

    def _process_data(self, data=None):
        if data is None:
            data = {}
        self.es_mipyme = data.get("es_mipyme", False)
        if data.get("razon_social"):
            self.name = data["razon_social"]
        if data.get("dte_email") and data["dte_email"].lower() not in [
            "facturacionmipyme2@sii.cl",
            "facturacionmipyme@sii.cl",
        ]:
            self.dte_email = data["dte_email"]
        if data.get("email"):
            self.name = data["email"]
        if data.get("telefono"):
            self.name = data["phone"]
        if data.get("direccion"):
            self.street = data["direccion"]
        if data.get("actecos"):
            acs = self.env["partner.activities"].sudo().search([("code", "in", data["actecos"])])
            self.acteco_ids = acs
        if data.get("glosa_giro"):
            query = [("name", "=", data.get("glosa_giro"))]
            ad = self.env["sii.activity.description"].search(query)
            if not ad:
                ad = self.env["sii.activity.description"].create({"name": data.get("glosa_giro")})
            self.activity_description = ad.id
        if data.get("url"):
            self.website = data["url"]
        if data.get("logo"):
            self.image_1920 = data["logo"]
        self.sync = True
        if not self.document_number:
            self.document_number = data["rut"]
        self.last_sync_update = data["actualizado"]

    def put_remote_user_data(self, url, data):
        try:
            resp = pool.request(
                "PUT",
                url,
                body=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            message = ""
            title = "Advertencia"
            if resp.status != 200:
                _logger.warning("Error en conexión al sincronizar partners %s" % resp.data)
                title = "Error en conexión al sincronizar partners"
                if resp.status == 403:
                    data = json.loads(resp.data.decode("ISO-8859-1"))
                    message = data["message"]
                else:
                    message = str(resp.data)
            else:
                try:
                     data = json.loads(resp.data.decode("ISO-8859-1"))
                     if data:
                        message = data.get('message')
                except:
                     message = "Respuesta inesperada o vacía desde la api: %s " % str(resp.data)

            if message:
                _logger.warning(message)
                """self.env["bus.bus"].sendone(
                    (self._cr.dbname, "res.partner", self.env.user.partner_id.id),
                    {
                        "title": title,
                        "message": message,
                        "url": "res_config",
                        "type": "dte_notif",
                    },
                )"""
        except:
            _logger.error("Error en PUT partner", exc_info=True)

    def get_data_to_put(self):
        if self.document_number in [False, 0, "0"]:
            return {}
        return {
            "rut": self.document_number,
            "glosa_giro": self.activity_description.name,
            "razon_social": self.name,
            "dte_email": self.dte_email,
            "email": self.email,
            "direccion": self.street,
            # 'comuna': self.
            "telefono": self.phone,
            "actecos": [ac.code for ac in self.acteco_ids],
            "url": self.website,
            "logo": self.image_1920.decode() if self.image_1920 else False,
        }

    def get_remote_user_data(self, to_check, process_data=True):
        company = self.company_id or self.env.company
        url = company.url_remote_partners
        token = company.token_remote_partners
        if not url or not token:
            return
        if to_check in [False, 0, "0"]:
            return
        try:
            resp = pool.request(
                "POST",
                url,
                body=json.dumps({
                    "rut": to_check,
                    "token": token,
                    "version": 1.0,}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            message = ""
            title = "Advertencia"
            if resp.status != 200:
                _logger.warning("Error en conexión al obtener partners %s" % resp.data)
                title = "Error en conexión al obtener partners"
                process_data = False
                if resp.status == 403:
                    data = json.loads(resp.data.decode("ISO-8859-1"))
                    message = data["message"]
                else:
                    message = str(resp.data)
            else:
                data = json.loads(resp.data.decode("ISO-8859-1"))
                message = data.get('message')
            if message:
                self.env["bus.bus"].sendone(
                    (self._cr.dbname, "res.partner", self.env.user.partner_id.id),
                    {
                        "title": title,
                        "message": message,
                        "url": "res_config",
                        "type": "dte_notif",
                    },
                )
            if not process_data:
                return data
            if not data:
                self.sync = False
                return
            self._process_data(data)
        except:
            _logger.error("Error en get remote partner", exc_info=True)

    @api.onchange("name")
    def fill_partner(self):
        if self.sync:
            return
        if self.document_number and self.check_vat_cl(self.document_number.replace(".", "").replace("-", "")):
            self.get_remote_user_data(self.document_number)
        elif self.name and self.check_vat_cl(self.name.replace(".", "").replace("-", "")):
            self.get_remote_user_data(self.name)

    @api.model
    def _check_need_update(self, groups=100):
        to_sync = {}
        rut_sync = {}
        recs = self.search([("document_number", "not in", [False, 0]), ("parent_id", "=", False)])
        multi = len(recs) > 1
        i = 0
        for r in recs:
            company = r.company_id or self.env.company
            url = company.url_remote_partners
            token = company.token_remote_partners
            if not url or not token:
                continue
            to_sync.setdefault((url, token, i), {
                "token": token,
                "version": 2.0,
                "origen": self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            })
            if company.sync_remote_partners:
                data = r.get_data_to_put()
                if not data:
                    continue
                rut_sync[data['rut']] = r
                if multi:
                    to_sync[(url, token, i)].setdefault("ruts", {})
                    to_sync[(url, token, i)]["ruts"][r.document_number] = data
                    if len(to_sync[(url, token, i)]["ruts"]) == groups:
                        i+=1
                else:
                    to_sync[(url, token, i)].update(data)
        for k, data in to_sync.items():
            try:
                self.put_remote_user_data(k[0], data)
            except:
                _logger.warning("Error al hacer PUT", exc_info=True)
            try:
                if multi:
                    ruts = {}
                    for r, rut_data in data['ruts'].items():
                        ruts[r] = {
                            "rut": rut_data['rut'],
                            "actualizado": str(rut_sync[rut_data['rut']].last_sync_update),
                        }
                    resp = pool.request(
                        "POST", k[0],
                        body=json.dumps({
                            "ruts": ruts,
                            "token": k[1],
                            "version": 2.0,
                        }).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    resp = pool.request(
                        "GET", k[0], {
                            "token": k[1],
                            "version": 2.0,
                            "rut": data['rut'],
                            "actualizado": rut_sync[data['rut']].last_sync_update,
                        }
                    )
                message = ""
                title = "Advertencia"
                if resp.status != 200:
                    _logger.warning("Error en conexión al consultar partners %s" % resp.data)
                    title = "Error en conexión al consultar partners"
                    if resp.status == 403:
                        data = json.loads(resp.data.decode("ISO-8859-1"))
                        message = data["message"]
                    else:
                        message = str(resp.data)
                else:
                    data = json.loads(resp.data.decode("ISO-8859-1"))
                    message = data.get('message')
                    result = data.get("result", False)
                    if result:
                        if multi:
                            for rut, valores in result['ruts'].items():
                                if valores['result']:
                                    r = rut_sync[rut]
                                    r._process_data(valores)
                        else:
                            r = rut_sync[data.get("rut", False)]
                            r._process_data(result)

                if message:
                    self.env["bus.bus"].sendone(
                        (self._cr.dbname, "res.partner", self.env.user.partner_id.id),
                        {
                            "title": title,
                            "message": message,
                            "url": "res_config",
                            "type": "dte_notif",
                        },
                    )
            except:
                _logger.error("Error en need_update", exc_info=True)
