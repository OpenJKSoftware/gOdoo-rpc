"""Provide Odoo Excel import Class and Methods."""


import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from odoorpc import ODOO
from openpyxl import Workbook, load_workbook

from ..helpers import OdooImporter
from .import_data import OdooDataImporter
from .import_settings import OdooSettingsImporter
from .import_translation import OdooTranslationImporter

logger = logging.getLogger(__name__)


class OdooXLImporter(OdooImporter):
    """Provide data pulling from a Excel File."""

    def __init__(self, session: ODOO, file_path: Path, max_batch_size: int = 256) -> None:
        """Initialize OdooXLImporter.

        Parameters
        ----------
        session : ODOO
            Odoo Session
        file_path : Path
            Excel FilePath
        max_batch_size : int, optional
            Max num of recrords to send to Odoo at once, by default 256
        """
        self.path = file_path
        self._workbook: Optional[Workbook] = None
        self.max_batch_size = max_batch_size
        super().__init__(session=session)

    @property
    def workbook(self) -> Workbook:
        """Openpyxl workbook. Cached.

        Returns
        -------
        Workbook
            OpenpyXL Workbook

        Raises
        ------
        FileNotFoundError
            Couldn't find/open workbook
        """
        if not self._workbook:
            self._workbook = load_workbook(str(self.path), read_only=True)
        if not self._workbook:
            raise FileNotFoundError(f"Workbook {self.path} Not Loaded")
        return self._workbook

    def import_sheets_by_regex(self, regex_pattern: str) -> None:
        """Import all Worksheets with name matching regex into the odoo module defined in the regex.

        Parameters
        ----------
        regex_pattern : str
            Regex pattern with named group "module"
        """
        worksheets = self.workbook.worksheets

        import_sheets = {match: s for s in worksheets if (match := re.search(regex_pattern, str(s.title)))}
        importer = OdooDataImporter(session=self.session)
        for index, (match, sheet) in enumerate(import_sheets.items(), 1):
            odoo_model = match.group("model")
            logger.info(
                "(%s/%s) Importing Worksheet: %s into Module %s", index, len(import_sheets), sheet.title, odoo_model
            )
            sheet_data = pd.read_excel(str(self.path.resolve()), sheet.title)

            importer.upload(
                source_str=str(self.path.stem) + str("!") + str(sheet.title),
                model_name=odoo_model,
                dataframe=sheet_data,
                max_batch_size=self.max_batch_size,
            )

    def import_settings(self, sheet_name: str) -> None:
        """Import Odoo Settings from Excel Sheet Table.

        Parameters
        ----------
        sheet_name : str
            Sheet to import
        """
        settings_importer = OdooSettingsImporter(self.session)
        sheet_data: pd.DataFrame = pd.read_excel(str(self.path.resolve()), sheet_name=sheet_name)

        sheet_data = sheet_data.fillna("")
        for lang, group in sheet_data.groupby("Language"):
            lang_settings: Dict[str, Any] = pd.Series(
                group["Value"].values, index=group["Setting"].values  # type: ignore
            ).to_dict()
            settings_importer.import_settings(lang_settings, str(lang))

    def install_modules(self, sheet_name: str) -> None:
        """Install Modules Provided by List.

        Parameters
        ----------
        sheet_name : str
            Sheetname with "Name" column
        """
        settings_importer = OdooSettingsImporter(self.session)
        sheet_data: pd.DataFrame = pd.read_excel(str(self.path.resolve()), sheet_name=sheet_name)
        settings_importer.install_modules(sheet_data["Name"].tolist())

    def import_translations(self, sheet_name: str) -> None:
        """Import Translations from Excel sheet.

        Parameters
        ----------
        sheet_name : str
            excel sheetname
        """
        translation_importer = OdooTranslationImporter(self.session)
        sheet_data: pd.DataFrame = pd.read_excel(str(self.path.resolve()), sheet_name=sheet_name)
        translation_importer.import_translations(sheet_data)
