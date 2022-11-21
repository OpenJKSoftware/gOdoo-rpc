"""Provide Odoo CSV import Class and Methods."""

import csv
import io
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Match

import numpy as np
import pandas as pd
from odoorpc import ODOO
from odoorpc.models import Model

from ..helpers import OdooImporter

logger = logging.getLogger(__name__)
LANG_COL_REGEX = re.compile(r"(?P<col>.*):lang:(?P<lang>.*)")


@dataclass
class LangPair:
    """Store a col -> languagecol relation."""

    id_col: str  # DF Col for Odoo affected External ID
    val_col: str  # DF Col for Lang Value
    field_name: str  # Odoo FieldName
    lang: str  # Odoo Context Language


def dataframe_get_lang_cols(dataframe: pd.DataFrame) -> Dict[str, Match[str]]:
    """Get Language Cols in Upload Dataset (fieldname:lang:en_US).

    Parameters
    ----------
    dataframe : pd.DataFrame
        dataframe with col names in sytle: fieldname:lang:en_US

    Returns
    -------
    Dict[str, re.Match[str]]
        dict of colname and re.match
    """
    return {col: re_match for col in dataframe.columns if (re_match := LANG_COL_REGEX.match(col))}


def dataframe_strip_language(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Remove Language cols (see dataframe_get_lang_cols) from Dataframe.

    Parameters
    ----------
    dataframe : pd.DataFrame
        dataframe to remove cols from

    Returns
    -------
    pd.DataFrame
    """
    lang_cols = dataframe_get_lang_cols(dataframe=dataframe)
    other_cols = [col for col in dataframe.columns if col not in lang_cols]
    return dataframe[other_cols]


def dataframe_generate_lang_pairs(dataframe: pd.DataFrame) -> List[LangPair]:
    """Generate Language Pairs from Dataframe Columns.

        Each Pair Links the FieldCol to the Language col and the affected ID col.

    Parameters
    ----------
    dataframe : pd.DataFrame
        dataframe to scan for language cols

    Returns
    -------
    List[LangPair]
    """
    lang_cols = dataframe_get_lang_cols(dataframe=dataframe)
    lang_pairs: List[LangPair] = []
    for col, match in lang_cols.items():
        lang = str(match.group("lang"))
        ref_col = str(match.group("col"))
        id_col = ""
        if "/" in ref_col:
            splits = ref_col.split("/")
            try_index = 1
            while not id_col:
                id_try = "/".join(splits[:-try_index] + ["id"])
                if id_try in dataframe.columns:
                    id_col = id_try
                    ref_col = ".".join(splits[-try_index:])
        else:
            id_col = "id"
        lang_pairs.append(LangPair(id_col=id_col, val_col=col, field_name=ref_col, lang=lang))
    return lang_pairs


def chunk_odoo_import(full_data: pd.DataFrame, chunk_size: int) -> List[pd.DataFrame]:
    """Split Dataframe into chunks of max length. Can overflow a chunk until "id" column is not nan.

    Parameters
    ----------
    full_data : pd.DataFrame
        input dataframe
    chunk_size : int
        cutoff chunk size

    Returns
    -------
    List[pd.DataFrame]
        chunked dataframe
    """
    if len(full_data) <= chunk_size:
        return [full_data]

    logger.debug("Chunking Dataset with %s Entries to size %s", len(full_data), chunk_size)
    chunk_count = -(-len(full_data) // chunk_size)  # Round Number of slices up
    chunks: List[pd.DataFrame] = np.array_split(full_data, chunk_count)  # type: ignore
    out_chunks: List[pd.DataFrame] = [chunks.pop(0)]  # Remove First Chunk and add to Output
    for index, chunk in enumerate(chunks):

        empty_ids = pd.isnull(chunk.id)  # Check Empty Ids

        if empty_ids.all():
            # No Ids at all? Append chunk to last Output chunk
            out_chunks[-1] = out_chunks[-1].append(chunk)  # type: ignore
            continue

        if not empty_ids.any():
            # No Empty Ids.. Just add Chunk to outlist
            out_chunks.append(chunk)
            continue

        move_rows_count = np.where(~empty_ids)[0][0]  # Get index of first Non empty Id.

        logger.debug("(%s/%s) Move %s rows to Previous Chunk", index + 1, len(chunks), move_rows_count)
        move_rows = chunk.iloc[0:move_rows_count]
        out_chunks[-1] = out_chunks[-1].append(move_rows)  # type: ignore
        if not (out_chunk := chunk.drop(list(move_rows.index))).empty:
            out_chunks.append(out_chunk)

    logger.info("Dataframe with len %s chunked into %s parts", len(full_data), len(out_chunks))
    return out_chunks


class OdooDataImporter(OdooImporter):
    """Provide data pulling from a CSV File.

    Dataframe needs to be in standard Odoo Format.

    In addition there are some extra features:

    Suffix a column with ":lang:langCoge" example: "name:lang:en_US"
        This will add Translations in the sepecified language
    """

    def __init__(
        self,
        session: ODOO,
    ) -> None:
        """Construct OdooDataImporter.

        Parameters
        ----------
        session : ODOO
            Odoo Session

        """
        self._source = ""
        self._model_name = ""
        self._max_batch_size = 0
        self._dialect = csv.excel
        super().__init__(session=session)

    @property
    def model_name(self) -> str:
        """Expose Model_Name as ReadOnly Property.

        Returns
        -------
        str
            Odoo Model Name
        """
        return self._model_name

    def _df2upload_file(self, data: pd.DataFrame) -> str:
        """Convert Dataframe into OdooRPC Upload String.

        Parameters
        ----------
        data : pd.DataFrame
            Model data

        Returns
        -------
        str
            CSV String
        """
        csv_sio = io.StringIO()
        data.to_csv(
            csv_sio,
            encoding="utf-8",
            sep=self._dialect.delimiter,
            date_format="%Y-%m-%d %H:%M:%S",
            index=False,
            quotechar=self._dialect.quotechar or "",
            line_terminator=self._dialect.lineterminator,
            escapechar=self._dialect.escapechar,
        )  # Convert back to in memory csv
        return csv_sio.getvalue()

    def _import_translations(self, dataframe: pd.DataFrame) -> None:
        lang_pairs = dataframe_generate_lang_pairs(dataframe=dataframe)
        if not lang_pairs:
            return
        logger.info("Found: %s Language Columns", len(lang_pairs))
        for index, pair in enumerate(lang_pairs, 1):
            logger.info("(%s/%s) Processing Language %s, Col: %s", index, len(lang_pairs), pair.lang, pair.val_col)
            for _, row in dataframe.iterrows():
                if pd.notna(row[pair.val_col]):
                    odoo_rec: Model = self.session.env.ref(row[pair.id_col])
                    odoo_rec = odoo_rec.with_context(lang=pair.lang).write({pair.field_name: row[pair.val_col]})

    def _strip_existing_records(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Remove Records, form Dataframe if the id is already registered in odoo ir.model.data.

        Parameters
        ----------
        dataframe : pd.DataFrame
            input dataframe with "id" column

        Returns
        -------
        pd.DataFrame
            filtered dataset
        """
        xml_ids = dataframe.id.dropna().drop_duplicates().str.split(".", n=1, expand=True)
        odoo_model_data: Model = self.session.env["ir.model.data"]
        existing_ids = odoo_model_data.search_read(
            [
                "&",
                ("name", "in", list(xml_ids[1])),
                ("module", "in", list(xml_ids[0])),
            ],
            fields=["name", "module"],
        )
        if not existing_ids:
            return dataframe
        odoo_xml_id_df = pd.DataFrame(existing_ids)
        odoo_xml_ids = odoo_xml_id_df["module"] + "." + odoo_xml_id_df["name"]

        return dataframe[~dataframe.id.ffill().isin(odoo_xml_ids)]

    def upload(
        self,
        dataframe: pd.DataFrame,
        model_name: str,
        max_batch_size: int = 0,
        source_str: str = "Internal",
        skip_existing_ids: bool = False,
    ) -> None:
        """Upload Dataframe to Odoo.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Dataframe to upload. Must contain "id" column
        model_name : str
            Odoo Model Name
        max_batch_size : int
            Max Rows to sent in one Import action , by default len(dataframe)
        source_str : str, optional
            Just for Logging, datasource, by default "Internal"
        skip_existing_ids : bool, optional
            Wether to first query Odoo for Ids and skip them if neccessary

        Raises
        ------
        IndexError
            When there are Duplicate IDs in the Dataframe
        """
        self._source = source_str or ""
        self._model_name = model_name
        self._max_batch_size = max_batch_size if max_batch_size > 0 else len(dataframe)

        logger.info("Staring Import from '%s' to '%s'", self._source, self._model_name)
        if dataframe.empty:
            logger.error("Cant import %s. No Data Provided", self._source)
            return

        if (dupe_mask := dataframe["id"].replace("", np.nan).dropna().duplicated()).any():
            dupes = dataframe.dropna(subset=["id"]).loc[dupe_mask, "id"]
            logger.error("Detetced duplicate Ids in %s. Dupes: %s", self._source, dupes)
            raise IndexError(f"Detedced duplicate Ids in {self._source}. Dupes:\n{dupes}")

        if skip_existing_ids:
            dataframe = self._strip_existing_records(dataframe)
            if dataframe.empty:
                logger.info("All IDs in Dataframe already exist in Odoo")
                return

        dataframe = dataframe.loc[:, ~dataframe.columns.str.contains("^Unnamed")]

        self._upload_chunked(dataframe)

    def _upload_chunked(self, dataframe: pd.DataFrame) -> None:
        """Upload the Specified Dataframe chunked.

        Parameters
        ----------
        dataframe : pd.DataFrame
            dataframe to upload
        """
        no_lang_df = dataframe_strip_language(dataframe=dataframe)
        no_empty_rows = no_lang_df.dropna(how="all", axis=0)
        chunks = chunk_odoo_import(no_empty_rows, self._max_batch_size)
        for index, chunk in enumerate(chunks, 1):
            logger.info(
                "(%s/%s) Importing %s records from '%s' into Odoo", index, len(chunks), len(chunk), self._source
            )
            self._upload(chunk, index)
        self._import_translations(dataframe)

    def _upload(self, dataset: pd.DataFrame, index: int = 1) -> None:
        """Create a base_import transient model and commits provided data it to odoo.

        Parameters
        ----------
        dataset : pd.DataFrame
            Dataset to upload
        index : int, optional
            folename index for logging in case of chunked upload, by default 1
        """
        odoo_model: Model = self.session.env["base_import.import"]
        up_data = self._df2upload_file(dataset)

        imp_id = odoo_model.create(
            {
                "res_model": self._model_name,
                "file": up_data,
                "file_type": "text/csv",
                "file_name": self._source + f"-{index}",
            }
        )
        logger.debug("Odoo: Created 'base.import' model with id : %s", imp_id)
        imp = odoo_model.browse(imp_id)

        headers = list(dataset.columns.values)

        resp = imp.do(
            headers,
            headers,
            {
                "headers": True,
                "advanced": True,
                "keep_matches": False,
                "date_format": "%Y-%m-%d %H:%M:%S",
                "datetime_format": "%Y-%m-%d %H:%M:%S",
                "encoding": "utf-8",
                "separator": self._dialect.delimiter,
                "quoting": self._dialect.quotechar,
                "float_thousand_separator": ",",
                "float_decimal_separator": ".",
            },
        )

        if messages := resp["messages"]:
            self.handle_upload_errors(messages, dataset)

        expect_len = len(dataset["id"].dropna().unique())
        if len(resp["ids"]) != expect_len:
            logger.error("Expected %s, Records to be imported, but odoo only reports %s", expect_len, len(resp["ids"]))

    def handle_upload_errors(self, messages: List[Dict[str, Any]], dataset: pd.DataFrame) -> None:
        """Handle Error Messages.

        Parameters
        ----------
        messages : List[Dict[str, Any]]
            Response from Upload
        dataset : pd.DataFrame
            The Reference Dataset

        Raises
        ------
        ImportError
            If an error Occured
        """
        logger.error("Odoo Import Failed with message:\n%s", json.dumps(messages, sort_keys=True, indent=2))
        messages = [m for m in messages if "rows" in m]
        affected_row_pairs = [(int(m["rows"]["from"]), int(m["rows"]["to"])) for m in messages]
        affected_rows = [row for lower, upper in affected_row_pairs for row in range(lower, upper + 1)]
        err_df = dataset.iloc[list(set(affected_rows))]

        affected_fields: List[str] = [str(m.get("field")) for m in messages] + ["id"]
        affected_cols: List[str] = []
        for col in affected_fields:  # Need to add /id or /name if we are talking about a relational field
            if col in err_df.columns:
                affected_cols.append(col)
            elif col + "/id" in err_df.columns:
                affected_cols.append(col + "/id")
            elif col + "/name" in err_df.columns:
                affected_cols.append(col + "/name")

        err_df = err_df[[c for c in err_df.columns if c in affected_cols]]  # Looks weird, but preserves DF Col Order
        with pd.option_context("display.max_rows", None, "display.max_columns", None):  # type: ignore
            logger.error("Relevant Dataset:\n%s", err_df)
        raise ImportError("Odoo Responded with errors. See log.")
