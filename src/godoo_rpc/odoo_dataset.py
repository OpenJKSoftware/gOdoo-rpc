"""Facilitates Odoo Odoo FileImports."""

import importlib.util
import json
import logging
import re
import sys
from datetime import datetime
from importlib.abc import Loader
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from j_pandas_datalib import Dataset

from .api import OdooApiWrapper

FOLDER_REGEX = re.compile(r"(\d+)_.*")

_logger = logging.getLogger(__name__)


class OdooDataset(Dataset):
    """Class to Map Dataset to File and Odoo_Model."""

    def __init__(
        self,
        file: Path,
        dataframe: pd.DataFrame = None,
        reference: str = "",
        read_only: bool = False,
    ) -> None:
        """Construct OdooDataset.

        Parameters
        ----------
        file : Path
            FilePath
        dataframe : pd.DataFrame, optional
            Data, by default None
        reference : str, optional
            Reference for API, by default ""
        read_only : bool, optional
            prevent save method
        """
        self.is_script = False
        if file:
            if file.suffix == ".py":
                read_only = True
                self.is_script = True
        super().__init__(file, dataframe=dataframe, reference=reference, read_only=read_only)

    def sort_key(self, max_up_folder: Path) -> str:
        """Traverse up the Path Tree to build sortable path.

        Parameters
        ----------
        max_up_folder : Path
            stop at partent

        Returns
        -------
        str
            sort string
        """
        sort_list = [self.file.name]
        for par in self.file.parents:
            if FOLDER_REGEX.match(par.name):
                sort_list.append(par.name)
            if par == max_up_folder:
                break
        return "/".join(reversed(sort_list))


def import_settings_from_df(odoo_api: OdooApiWrapper, dataframe: pd.DataFrame) -> None:
    """Load Odoo Settings from col "Value" into setting from Col "Setting".

    Values with a "Language" specified will be loaded into the Language

    Parameters
    ----------
    odoo_api : OdooApiWrapper
        Odoo Api wrapper
    dataframe : pd.DataFrame
        Settings DF. Columns: "Setting,Value,Language"
    """
    dataframe.Language = dataframe.Language.fillna(False)
    for lang, group in dataframe.groupby("Language", sort=False):
        lang_settings: Dict[str, Any] = pd.Series(
            group["Value"].values, index=group["Setting"].values  # type: ignore
        ).to_dict()

        odoo_api.settings_importer.import_settings(lang_settings, str(lang) if not pd.isna(lang) else "")


def import_by_script(odoo_api: OdooApiWrapper, dataset: OdooDataset) -> None:
    """Run Method Main(odoo_api) in Python script.

    Parameters
    ----------
    odoo_api : OdooApiWrapper
        Odoo Api Wrapper
    dataset : OdooDataset
        Odoo Dataset CLass

    Raises
    ------
    ModuleNotFoundError
        Could not import Module
    ImportError
        Could not load Spec
    """
    _logger.debug("Attempting to load python Module: %s", dataset.file)
    spec = importlib.util.spec_from_file_location("odoo_data_import", dataset.file.absolute())
    if not spec:
        raise ModuleNotFoundError(f"Couldnt Load '{dataset.file.absolute()}' as module")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    if not isinstance(spec.loader, Loader):
        raise ImportError(f"Couldnt Load Spec from '{dataset.file.absolute()}'")
    spec.loader.exec_module(mod)
    _logger.info("Launching Main Method in Import Script: %s", dataset.file)
    mod.Main(odoo_api)  # type: ignore


def import_model_data(
    odoo_api: OdooApiWrapper,
    data: OdooDataset,
    skip_existing_ids: bool = False,
) -> None:
    """Import Data into Odoo using base.import.

    Parameters
    ----------
    odoo_api : OdooApiWrapper
        Odoo API Wrapper
    data : OdooDataset
        OdooDataset
    skip_existing_ids : bool, optional
        Skip Ids that already exist in Odoo, by default False
    """
    if data.is_script:
        import_by_script(odoo_api=odoo_api, dataset=data)
        return

    odoo_api.data_importer.upload(
        data.dataframe, data.reference, 256, data.file.name, skip_existing_ids=skip_existing_ids
    )


def import_dataset(data: OdooDataset, odoo_api: OdooApiWrapper, skip_existing_ids: bool = False) -> None:
    """Import Dataset into Odoo Modules.

    Parameters
    ----------
    data : OdooDataset
        Import Dataset for Odoo Model or Archive
    odoo_api : OdooApiWrapper
        Odoo Api
    skip_existing_ids : bool, optional
        Skip Ids that already exist in Odoo, by default False

    Special Odoo "Modules":
        odoo-modules:
            all modules specified in col "Name" will be installed
        odoo-settings:
            Sets res.config.settings
            settings from col "Setting" will be set to col "Value"
            Optional col "Language" can specify the Lanuage to set.
        odoo-translate:
            translates Odoo Fields
            Col pattern is language/fieldname. Example: en_US/name
            'id' must be the first column

    Special Actions for Modules:
        stock.inventory:
            All imported inventories will get action_start and action_validate called after import.
    """
    if data.reference == "odoo-modules":
        _logger.info("Installing modules from '%s' into Odoo", data.file.name)
        odoo_api.settings_importer.install_modules(data.dataframe.Name.unique())

    elif data.reference == "odoo-settings":
        _logger.info("Importing Settings from '%s' into Odoo", data.file.name)
        import_settings_from_df(odoo_api=odoo_api, dataframe=data.dataframe)

    elif data.reference == "odoo-translate":
        _logger.info("Importing Translation from '%s' into Odoo", data.file.name)
        odoo_api.translation_importer.import_translations(data.dataframe)

    elif data.reference == "odoo-unarchive":
        unarch_ids = data.dataframe.id.unique()
        _logger.info("Unarchiving Items %s from '%s'", len(unarch_ids), data.file.name)
        for xml_id in unarch_ids:
            if not (odoo_rec := odoo_api.session.env.ref(xml_id)).active:
                _logger.debug("Unarchiving '%s' --> '%s'", xml_id, odoo_rec.name)
                odoo_rec.action_unarchive()

    elif data.reference == "odoo-archive":
        unarch_ids = data.dataframe.id.unique()
        _logger.info("Archiving Items %s from '%s'", len(unarch_ids), data.file.name)
        for xml_id in unarch_ids:
            if not (odoo_rec := odoo_api.session.env.ref(xml_id)).active:
                _logger.debug("Archiving '%s' --> '%s'", xml_id, odoo_rec.name)
                odoo_rec.action_archive()

    else:
        _logger.info("Importing '%s' into Odoo module '%s'", data.file.name, data.reference)
        import_model_data(odoo_api=odoo_api, data=data, skip_existing_ids=skip_existing_ids)


def import_dataset_timestamped(
    dataset: OdooDataset, odoo_api: OdooApiWrapper, relative_folder: Path, skip_existing_ids: bool = False
) -> None:
    """Call import_dataset, log Timestamp in ir.config.parameter and skip if timestamp is smaller.

    Parameters
    ----------
    dataset : OdooDataset
        Upload Datase
    odoo_api : OdooApiWrapper
        Logged in API Wrapper
    relative_folder : Path
        Folder to which odoo dataset paths are relative to
    skip_existing_ids : bool, optional
        Skip Ids that already exist in Odoo, by default False
    """
    paramteter_model = odoo_api.session.env["ir.config_parameter"]

    continue_import = True
    import_ref = dataset.file.relative_to(relative_folder)
    odoo_ref_name = "godoo_rpc_import_cache"
    change_date_fs = datetime.fromtimestamp(dataset.file.stat().st_mtime)

    import_ref_search = paramteter_model.search([("key", "=", odoo_ref_name)])
    odoo_import_ref = paramteter_model.browse(import_ref_search[0]) if import_ref_search else None

    change_dict = {}
    if odoo_import_ref:
        change_dict = json.loads(odoo_import_ref.value)
        if ref_entry := change_dict.get(str(import_ref)):
            odoo_change_date = datetime.fromisoformat(ref_entry)
            if change_date_fs <= odoo_change_date:
                _logger.debug("Skipping Import file because of Timestamp in Odoo: %s", dataset.file.absolute())
                continue_import = False

    if continue_import:
        import_dataset(data=dataset, odoo_api=odoo_api, skip_existing_ids=skip_existing_ids)
        change_dict.update({str(import_ref): change_date_fs.isoformat()})
        if odoo_import_ref:
            odoo_import_ref.value = json.dumps(change_dict)
        else:
            paramteter_model.create({"key": odoo_ref_name, "value": json.dumps(change_dict)})
