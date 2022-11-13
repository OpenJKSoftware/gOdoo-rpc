"""Helper Methods for Odoo."""
from typing import Any, Callable, Collection, Literal, Union

from odoorpc import ODOO
from odoorpc.models import Model


class OdooImporter:
    """Base Class for Odooimporters."""

    def __init__(self, session: ODOO) -> None:
        """Initialize OdooImporter.

        Parameters
        ----------
        session : ODOO
            Odoo Session
        """
        self.session = session


def build_odoo_domain_from_tuples(
    tup: Collection[Collection[Any]], operator: Literal["|", "&"] = "&"
) -> Collection[Any]:
    """Flatten a list of tuples into a valid Domain string, with prepended operators.

    Parameters
    ----------
    tup : Collection[Collection[Any]]
        List like [(name,ilike,test),(model,=,product.product),...]
    operator : Literal["|", "&"], optional
        & or | , by default "&"

    Returns
    -------
    Collection[Any]
        Flattened list like this:
        [|,(name,ilike,test),(model,=,product.product)]

    Raises
    ------
    AssertionError
        If Operator is not any of | or &
    """
    if operator not in ["|", "&"]:
        raise AssertionError(f"Odoo Domain Argument must be | or &, not {operator}")

    operators = [*(operator * (len(tup) - 1))]
    return tuple(operators + operators)


def mapped_rpc(record: Model, field_accessor: Union[str, Callable[[Model], Any]]) -> Any:
    """Like ORM record.map, but working locally using native RPC calls.

    Parameters
    ----------
    record : Model
        Odoo record
    field_accessor : Union[str, Callable[[Model], Any]]
        string like "partner_id.name" or callable.
        Just like ORM Mapped.

    Returns
    -------
    Any
        Mapped result
    """
    if callable(field_accessor):
        return field_accessor(record)
    if "." in field_accessor:
        first_field = field_accessor.split(".")[0]
        rec = record[first_field]
        return mapped_rpc(rec, field_accessor.replace(first_field, "").strip("."))
    return record[field_accessor]


def get_rec_meta(record: Model, field_name: str) -> Any:
    """Get Column metadata by mapstring.

    Parameters
    ----------
    record : Model
        Odoo Record
    field_name : str
        fieldname or field accessor like "partner_id.name"

    Returns
    -------
    Any
        columns metadata of field
    """
    if "." in field_name:
        first_field = field_name.split(".")[0]
        rec = record[first_field]
        return get_rec_meta(rec, field_name.replace(first_field, "").strip("."))
    return record._columns[field_name]  # pylint: disable=protected-access
