"""Module for res.config.settings importing."""

import logging
from typing import Any, Dict, List

from odoorpc.models import Model

from ..helpers import OdooImporter

logger = logging.getLogger(__name__)


class OdooSettingsImporter(OdooImporter):
    """Odoo handler for res.config.settings."""

    def import_settings(self, settings: Dict[str, Any], lang: str = "") -> None:
        """Create Transient res.config.settings model and executes it.

        Parameters
        ----------
        settings : Dict[str, str]
            dict of setting:value
        lang: str
            language string to set context to
        """
        settings_env: Model = self.session.env["res.config.settings"]

        for setting, value in settings.items():  # Replace Ref Attributes with their internal ID
            if hasattr(settings_env._columns[setting], "relation"):  # pylint: disable=protected-access
                settings[setting] = self.session.env.ref(value).id

        if lang:
            logger.info("Odoo preparing to set %s settings for language: %s", len(settings), lang)
            odoo_settings_id = settings_env.with_context(lang=lang).create([settings])
        else:
            logger.info("Odoo preparing to set %s settings", len(settings))
            odoo_settings_id = settings_env.create([settings])

        logger.info("Committing %s Settings to Odoo", len(settings))
        settings_env.execute(odoo_settings_id)  # Commit settings to Odoo

    def install_modules(self, modules: List[str]) -> None:
        """Install Odoo Modules by Name.

        Parameters
        ----------
        modules : List[str]
            List of Odoo module internal names
        """
        odoo_module_env: Model = self.session.env["ir.module.module"]
        odoo_module_env.update_list()
        logger.info("Installing %s Odoo Modules", len(modules))
        for index, module in enumerate(modules, 1):
            module_id = odoo_module_env.search([("state", "!=", "installed"), ("name", "=", module)])
            if module_id:
                logger.info("Odoo Installing Module (%s/%s): %s", index, len(modules), module)
                odoo_module_env.browse(module_id).button_immediate_install()
