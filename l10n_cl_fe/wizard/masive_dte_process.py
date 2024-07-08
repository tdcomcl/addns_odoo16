import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MasiveDTEProcessWizard(models.TransientModel):
    _name = "sii.dte.masive.process.wizard"
    _description = "SII Masive DTE Process Wizard"

    action = fields.Selection(
        [("create", "Crear"), ("accept", "Crear Aceptar Todos"), ("reject", "Crear Rechazar Todos"),],
        string="Acción",
        default="create",
        required=True,
    )

    
    def confirm(self):
        dtes = self.env["mail.message.dte"].browse(self._context.get("active_ids", []))
        if self.action == "create":
            dtes.pre_process()
        else:
            dtes.process(option=self.action)
