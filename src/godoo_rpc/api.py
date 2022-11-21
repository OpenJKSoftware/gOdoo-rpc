"""Wrapper scripts for OdooRPC."""
import logging
from pathlib import Path

from odoorpc import ODOO

from .importers import (
    OdooCsvImporter,
    OdooDataImporter,
    OdooImageImporter,
    OdooSettingsImporter,
    OdooTranslationImporter,
    OdooXLImporter,
)

logging.getLogger("odoorpc.rpc.jsonrpclib").setLevel(logging.INFO)


class OdooApiWrapper:
    """Wrap the Odoo RPC Api."""

    def __init__(self, odoo_session: ODOO) -> None:
        """Construct OdooApiWrapper.

        Parameters
        ----------
        odoo_session : ODOO
            Logged in Odoo session
        """
        self.session = odoo_session
        self.csv_importer = OdooCsvImporter(self.session)
        self.data_importer = OdooDataImporter(self.session)
        self.image_importer = OdooImageImporter(self.session)
        self.settings_importer = OdooSettingsImporter(self.session)
        self.translation_importer = OdooTranslationImporter(self.session)

    def xl_importer(self, file_path: Path, max_batch_size: int = 256) -> OdooXLImporter:
        """Return OdooXLImporter for the current session.

        Parameters
        ----------
        file_path : Path
            Path to the Excel file
        max_batch_size : int, optional
            max records to sent do oodoo in one request,, by default 256

        Returns
        -------
        OdooXLImporter
        """
        return OdooXLImporter(session=self.session, file_path=file_path, max_batch_size=max_batch_size)
