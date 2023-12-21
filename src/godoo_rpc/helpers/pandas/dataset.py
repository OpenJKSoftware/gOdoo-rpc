"""Metaclass for Datasets."""
import logging
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd

from godoo_rpc.helpers.pandas.read import pandas_read_csv

LOGGER = logging.getLogger(__name__)


class Dataset:
    """Class to bundle filesystem to dataframe."""

    def __init__(
        self,
        file: Path,
        dataframe: Optional[pd.DataFrame] = None,
        reference: str = "",
        read_only: bool = False,
        save_cols: Optional[List[str]] = None,
    ) -> None:
        """Construct Dataset.

        Parameters
        ----------
        file : Path
            FilePath
        dataframe : pd.DataFrame, optional
            Data, by default None
        reference : str, optional
            Reference for API, by default ""
        read_only : bool, optional
            prevent save method, by default False
        save_cols : List[str], optional
            list of columns to consider for saving, by defau
        """
        if isinstance(file, str):
            file = Path(file)
        self.file = file
        self._dataframe = dataframe
        self.reference = reference
        self._read_only = read_only
        self.save_cols = save_cols

    def _read(self, **kwargs: Any) -> pd.DataFrame:
        """Low Level Read method.

        Parameters
        ----------
        **kwargs : Any
            pass down to pandas.read_*

        Returns
        -------
        pd.DataFrame
            read dataframe

        Raises
        ------
        NotImplementedError
            no reader defined for file suffix
        ReferenceError
            File Not Found
        """
        if not self.file.exists():
            raise ReferenceError(f"File Not found: {self.file.absolute()}")
        if self.file.suffix == ".csv":
            return pandas_read_csv(self.file, **kwargs)
        if self.file.suffix == ".xlsx":
            return pd.read_excel(str(self.file.absolute()), **kwargs)
        if self.file.suffix == ".json":
            return pd.read_json(self.file, orient="table", precise_float=True, **kwargs)
        raise NotImplementedError(f"No Pandas load handler implemented for filetype {self.file.suffix}")

    def read(self, **kwargs: Any) -> pd.DataFrame:
        """Read the file to a Dataframe. Stores DF in this Class.

        Parameters
        ----------
        **kwargs : Any
            Pass down to _read

        Returns
        -------
        pd.DataFrame
            Content
        """
        LOGGER.info("Reading Dataset %s", self.file)

        if self._dataframe is None:
            self._dataframe = self._read(**kwargs)
        return self._dataframe

    @property
    def dataframe(self) -> pd.DataFrame:
        """Get the Dataframe. Reads file if Dataset is not set.

        Returns
        -------
        pd.DataFrame
        """
        if self._dataframe is None:
            self._dataframe = self.read()
        return self._dataframe

    @dataframe.setter
    def dataframe(self, dataframe: pd.DataFrame) -> None:
        """Setter for Dataframe.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Pandas Dataframe
        """
        self._dataframe = dataframe

    @property
    def save_dataframe(self) -> pd.DataFrame:
        """self.dataframe filtered by self.save_cols.

        Returns
        -------
        pd.DataFrame
            Dataframe for Save operation
        """
        my_df = self.dataframe
        if self.save_cols:
            return my_df[self.save_cols]
        return my_df

    def save(self, force_save: bool = False, **kwargs: Any) -> None:
        """Save Dataframe to Disk.

        Parameters
        ----------
        force_save : bool, optional
            wether to also save when there is no change
        **kwargs : Any
            Pass down to pandas.to_*

        Raises
        ------
        PermissionError
            File is marked Readonly
        NotImplementedError
            Unknown Fileformat
        """
        if self._read_only:
            raise PermissionError(f"Cant save '{self.file}'. Dataset is marked as Readonly.")
        save_df = self.save_dataframe
        if self.file.exists() and not force_save:
            if save_df.round(10).fillna("").equals(self._read().round(10).fillna("")):
                LOGGER.info(
                    "Skipping Save of Dataset with shape '%s' because the file '%s' didn't change",
                    self.dataframe.shape,
                    self.file,
                )
                return
        LOGGER.info("Saving Dataset with Shape %s to: %s", self.dataframe.shape, self.file)
        self.file.unlink(missing_ok=True)
        if self.file.suffix == ".csv":
            save_df.to_csv(self.file, index=False, **kwargs)
        elif self.file.suffix == ".xlsx":
            save_df.to_excel(self.file, index=False, **kwargs)
        elif self.file.suffix == ".json":
            save_df.to_json(self.file, orient="table", indent=4, **kwargs)
        else:
            raise NotImplementedError(f"No Save method for: {self.file.suffix}")
