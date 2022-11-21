"""Provide Odoo CSV import Class and Methods."""

import logging
from pathlib import Path

from j_pandas_datalib import pandas_read_csv
from odoorpc import ODOO

from ..helpers import OdooImporter
from .import_data import OdooDataImporter

logger = logging.getLogger(__name__)


class OdooCsvImporter(OdooImporter):
    """Provide data pulling from a CSV File."""

    def __init__(self, session: ODOO) -> None:
        """Construct OdooCsvImporter.

        Parameters
        ----------
        session : ODOO
            Odoo Session
        """
        super().__init__(session=session)
        self.importer = OdooDataImporter(session=self.session)

    def upload(
        self,
        file_path: Path,
        model_name: str,
        max_batch_size: int = 0,
    ) -> None:
        """Upload Csv to Odoo.

        Parameters
        ----------
        file_path : Path
            Path to CSV File
        model_name : str
            Odoo Model Name
        max_batch_size : int
            Max Rows to sent in one Import action , by default len(dataframe)
        """
        self.importer.upload(
            dataframe=pandas_read_csv(file_path=file_path),
            model_name=model_name,
            max_batch_size=max_batch_size or 0,
            source_str=str(file_path),
        )
