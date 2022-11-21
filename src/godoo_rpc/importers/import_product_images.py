"""Odoo Import API."""
import base64
import logging
import re
from pathlib import Path
from typing import Dict, List, Match, Tuple

from odoorpc.error import RPCError
from odoorpc.models import Model

from ..helpers import OdooImporter

logger = logging.getLogger(__name__)


class OdooImageImporter(OdooImporter):
    """Import images by regex into odoo."""

    def import_product_images(self, images: List[Tuple[str, Path]], overwrite_images: bool = False) -> None:
        """Search folder recursive for images matching a regex and then uploady matching ones to the odoo products.

        Parameters
        ----------
        images : List[tuple[str, Path]]
            mapping odoo default_code to image file
        overwrite_images : bool
            Wether Existing images should be overwritten
        """
        if not images:
            logger.debug("Skipping Product image Import. No Images Provided")
            return

        product_ids = tuple(v[0] for v in images)
        try:
            products_model: Model = self.session.env["product.product"]
        except RPCError:
            logger.warning("Cannot import Product images. Model product.product not found")
            return

        logger.info("Querying Odoo with %s product IDs", len(product_ids))

        prod_ids = products_model.search([("default_code", "in", product_ids)])
        if not overwrite_images:
            existing_images = self.session.env["ir.attachment"].search_read(
                [
                    ("res_field", "=", "image_1920"),
                    ("res_model", "=", "product.template"),
                    ("res_id", "in", prod_ids),
                ],
                fields=["res_id"],
            )
            logger.debug("Filtering %s products that already have an image", len(existing_images))
            existing_image_ids = [x["res_id"] for x in existing_images]
            prod_ids = [i for i in prod_ids if i not in existing_image_ids]

        if not prod_ids:
            return

        logger.info("Getting %s Products from Odoo", len(prod_ids))
        for index, prod_id in enumerate(prod_ids, 1):
            prod = products_model.browse([prod_id])
            dcode = prod.default_code
            logger.debug("Searching images for %s", dcode)
            match_images = [v[1] for v in images if v[0] == dcode]
            if match_images:
                selected_img = match_images[0]
                logger.info(
                    "(%s/%s) Setting Product image for '%s' --> '%s'", index, len(prod_ids), dcode, selected_img
                )
                img_b64 = base64.b64encode(selected_img.open("rb").read()).decode("utf-8")
                prod.image_1920 = img_b64

    def _files_by_regex(self, root_folder: Path, regex_pattern: str) -> Dict[Match[str], Path]:
        """Recursively searches for images by a regex.

        Parameters
        ----------
        root_folder : Path
            path to recursively scan for
        regex_pattern : str
            regex pattern to match against

        Returns
        -------
        Dict[re.Match[str], Path]
            dict of regex match and file
        """
        logger.info("Searching Product images in '%s' Regex: '%s'", root_folder, regex_pattern)
        regex = re.compile(regex_pattern)
        images = {f_match: f for f in root_folder.rglob("*") if (f_match := regex.match(f.name))}
        logger.debug("Found %s images", len(images))
        return images

    def search_images_by_regex(self, image_path: Path, regex_pattern: str) -> List[Tuple[str, Path]]:
        """Search folder recursive for images matching a regex and then uploady matching ones to the odoo products.

        Parameters
        ----------
        image_path : Path
            folder to scan for images
        regex_pattern : str
            regex pattern with named group "default_code". (Group is matched against odoo "default_code")

        Returns
        -------
        List[tuple[str,Path]]
            mapping default_code to image file
        """
        images = self._files_by_regex(image_path, regex_pattern)

        return [(m.group("default_code"), f) for m, f in images.items()]
