"""Csv Related Tools."""
import csv
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Type, Union

import pandas as pd

LOGGER = logging.getLogger(__name__)


def pandas_read_csv(
    file_path: Union[str, Path],
    decimal_char: Optional[str] = "",
    file_encoding: Optional[str] = "utf-8",
    **kwargs: Any,
) -> pd.DataFrame:
    """Read CSV File to dataframe and sniffs delimiter from first line.

    Columns that are Suffixed with ":type:typestring"
    will be explicitely converted.
    Example name:type:str will convert the column to string,
    and then remove ":type:str" from the colname

    Parameters
    ----------
    file_path : Union[str,PathLike]
        csv filepath to import
    decimal_char : str, optional
        pandas read decimal char. If empty will use . or , if dialect is ;
    file_encoding: str, optional
        encoding to open file with ,by default utf-8
    **kwargs : Any
        passed down to pd.read_csv

    Returns
    -------
    pd.DataFrame
    """
    file_path = Path(file_path) if not isinstance(file_path, Path) else file_path

    dialect = csv.Sniffer().sniff(file_path.open("r", encoding=file_encoding).readline())
    LOGGER.debug("Sniffed Dialect with delim: '%s' from %s", dialect.delimiter, file_path)

    decimal = decimal_char or "," if dialect.delimiter == ";" else "."

    typecols = _csv_read_type_cols(file_path, dialect, decimal)
    # fmt: on
    if typecols:
        renamer = {}
        type_dict: Dict[str, Any] = {}
        for org_col, (new_col, col_type) in typecols.items():
            renamer[org_col] = new_col
            type_dict[org_col] = col_type
        LOGGER.debug("Reading CSV with specific types for: %s", type_dict)
        type_csv: pd.DataFrame = pd.read_csv(
            str(file_path.absolute()),
            dialect=dialect,
            dtype=type_dict,
            **kwargs,
        )  # type: ignore
        return type_csv.rename(renamer, axis=1)

    if "engine" not in kwargs:
        kwargs["engine"] = "python"
    return pd.read_csv(file_path, dialect=dialect, decimal=decimal, **kwargs)  # type: ignore


def _csv_read_type_cols(file_path: Path, dialect: Type[csv.Dialect], decimal: str) -> Dict[str, Tuple[str, str]]:
    csv_header = pd.read_csv(file_path, dialect=dialect, decimal=decimal, nrows=0)  # type: ignore
    type_rx = re.compile("(?P<col>.*):type:(?P<type>.*)")
    # fmt: off
    typecols: Dict[str, Tuple[str, str]] = {
        str(col): (str(match.group("col")), str(match.group("type")))
        for col in csv_header
        if (match := type_rx.match(str(col)))
    }

    return typecols
