from odoo import SUPERUSER_ID, api
from facturacion_electronica import clase_util as fe_util
from base64 import b64encode
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    _logger.warning("Post Migrating l10n_cl_fe from version %s to 16.0.0.41.0" % installed_version)

    env = api.Environment(cr, SUPERUSER_ID, {})
    for r in env['mail.message.dte.document'].search([('xml','!=', '')]):
        xml = r.dte_id._parse_xml(b64encode(r.xml.encode('ISO-8859-1')))
        try:
            for dte in r._get_dtes(xml):
                Documento = dte.find("Documento")
                r.id_dte = Documento.get("ID")
        except:
            pass
