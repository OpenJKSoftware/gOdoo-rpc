"""Imports Data from Filesystem Tables into Odoo.

Files should be named in Schema:

001_Base/001_odoo.module.csv

Import order is Alphanumeric.
"""

import logging
import re
from pathlib import Path
from typing import List, Pattern

from .api import OdooApiWrapper
from .odoo_dataset import OdooDataset, import_dataset, import_dataset_timestamped

FOLDER_REGEX = re.compile(r"(\d+)_.*")

_logger = logging.getLogger(__name__)


def gather_import_files(datafolder: Path, regex_pattern: Pattern[str]) -> List[OdooDataset]:
    """Gather OdooDatasets by Regex.

    Parameters
    ----------
    datafolder : Path
        Folder to recursively search in
    regex_pattern : re.Pattern[str]
        regex pattern to match files on. Needs group "Module"

    Returns
    -------
    List[OdooDataset]
        List of Datasets
    """
    out_list = []
    for file in datafolder.rglob("*"):
        if match := regex_pattern.match(file.name):
            out_list.append(OdooDataset(file=file, reference=match.group("module")))

    out_list = sorted(out_list, key=lambda f: str(f.sort_key(datafolder)))

    return out_list


def import_data(
    read_path: Path,
    data_regex: str,
    product_image_regex: str,
    odoo_api: OdooApiWrapper,
    skip_existing_ids: bool = False,
    check_dataset_timestamp: bool = False,
) -> None:
    r"""Import Files found in folder.

    Files should be named index_odoo.module.csv.
    Folders can also be prepended with index_.
    Files will be sorted as a combination of all indices.

    Parameters
    ----------
    read_path : Path
        Folder to search for files or file to import
    data_regex : re.Pattern[str]
        Regex for Datafiles. Needs Group "Module"
    product_image_regex : re.Pattern[str]
        Regex for Image files. Example: (?P<default_code>\d{6})\.(jpeg|png|jpg)
    odoo_api : OdooApiWrapper
        logged in Odoo Api Instance
    skip_existing_ids : bool, optional
        Skip Ids that already exist in Odoo, by default False
    check_dataset_timestamp : bool, optional
        Log Import timestamps in ir.config_parameters. Skips Unchanged Datasets, by default false

    Raises
    ------
    NameError
        When the filename couldnt be parsed
    """
    data_regex_comp = re.compile(data_regex)

    if read_path.is_dir():
        import_files = gather_import_files(datafolder=read_path, regex_pattern=data_regex_comp)
    elif read_path.suffix == ".py":
        import_files = [OdooDataset(file=read_path, reference=read_path.stem)]
    elif match := data_regex_comp.match(read_path.name):
        import_files = [OdooDataset(file=read_path, reference=match.group("module"))]
    else:
        raise NameError(f"Couldnt Parse: {read_path.name}")
    _logger.info("Collected: %s files", len(import_files))
    max_index = len(import_files)
    for index, data in enumerate(import_files, 1):
        _logger.info("Processing Dataset (%s/%s) --> %s", index, max_index, data.reference)
        if check_dataset_timestamp:
            import_dataset_timestamped(
                dataset=data, odoo_api=odoo_api, skip_existing_ids=skip_existing_ids, relative_folder=read_path
            )
        else:
            import_dataset(data=data, odoo_api=odoo_api, skip_existing_ids=skip_existing_ids)

    if product_image_regex:
        product_image_regex_comp = re.compile(product_image_regex)

        image_files = odoo_api.image_importer.search_images_by_regex(
            read_path / "img", product_image_regex_comp.pattern
        )
        odoo_api.image_importer.import_product_images(image_files, overwrite_images=not skip_existing_ids)
