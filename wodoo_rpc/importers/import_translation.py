"""Module for res.config.settings importing."""

import logging

import pandas as pd
from odoorpc.models import Model

from ..helpers import OdooImporter

logger = logging.getLogger(__name__)


class OdooTranslationImporter(OdooImporter):
    """Odoo handler for res.config.settings."""

    def import_translations(self, dataframe: pd.DataFrame) -> None:
        """Import Translations by dataframe.

        Colnames need to be lang/fieldname. Example: en_US/name.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Dataframe with ID in first col
        """
        dataframe = dataframe.set_index("id")
        for index, (odoo_id, row) in enumerate(dataframe.iterrows(), 1):
            logger.info("Importing Translations into Odoo (%s/%s) ", index, len(dataframe))
            odoo_item: Model = self.session.env.ref(odoo_id)
            if odoo_item:
                for col in dataframe.columns:
                    if pd.notna(row[col]):
                        col_info = col.split("/")
                        lang = col_info[0]
                        model_field = ".".join(col_info[1:])
                        odoo_item = odoo_item.with_context(lang=lang)
                        odoo_item.write({model_field: row[col]})
