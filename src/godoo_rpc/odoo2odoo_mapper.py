"""Module to Facilitate the Translation from Odoo Records to another Instance."""
import datetime
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Union

from odoorpc.models import Model

from .helpers import get_rec_meta, mapped_rpc

logger = logging.getLogger(__name__)


def map_record_value(
    record_value: Any,
    record: Model,
    field: str,
    mapper: Dict[str, Any],
) -> Any:
    """Translate record value if its contained in mapper.

    Since Odoorpc returns many2one records as tuple (id,name) we are only interested in the id.
    Parameters
    ----------
    record_value : Any
        Value to Cleanup
    record : Model
        record from which the value was taken
    field : str
        field from wich the value was taken.
    mapper : Dict[str, Any]
        dict of {fiel_name:mapper}. where mapper = {source:target}.
        All fields with a mapper will get it's value swapped.
        Usually used to translate relational ids

    Returns
    -------
    Any
        Value i no mapper was found. Mapped value if mapper was found.
    """
    if record_value and get_rec_meta(record, field).type == "many2one":
        record_value = record_value[0]
    if mapper := mapper.get(field):  # type: ignore
        if isinstance(mapper, dict):
            if isinstance(record_value, list):
                return [mapper[v] for v in record_value]
            if hasattr(record_value, "id"):
                if len(record_value) > 1:
                    return [mapper[v] for v in record.ids]
                return mapper[record_value.id]
            return mapper[record_value]
    return record_value


def map_record_values(
    record: Model,
    mapper_dict: Dict[str, Union[str, Dict[Any, Any]]],
    ignore_map_errs: bool = False,
) -> Dict[str, Any]:
    """Return a Dict Value with Values mapped according to mapper_dict.

    Parameters
    ----------
    record : Model
        odoo_rpc component. All Keys in Mapper_dict will be read
    mapper_dict : Union[str, Dict[Any, Any]]
        dict of {"field_name":mapper}
        where mapper is a dict of {source:target}
    ignore_map_errs : bool, optional
        wether to just leave map errors empty, by default False

    Returns
    -------
    Dict[str,Any]
        Dict of fields:mapped_value

    Raises
    -----
    KeyError
        when value not found in mapper
    """
    record.ensure_one()
    record_values = record.read(list(mapper_dict.keys()))[0]
    del record_values["id"]
    for key, value in record_values.items():
        try:
            value = map_record_value(value, record, key, mapper_dict)
        except Exception as err:
            if ignore_map_errs:
                continue
            raise KeyError(f"Couldn't find {value} in mapper {key}. Record: {record}") from err

        record_values[key] = value
    return record_values


def format_domain_values(
    domain: Iterable[Union[str, Iterable[Any]]],
    record: Model,
    field_mappers: Dict[str, Union[str, Dict[Any, Any]]],
) -> Iterable[Union[str, Iterable[Any]]]:
    """Take in Domain with %()s string templates.

    Parameters
    ----------
    domain : Iterable[Union[str, Iterable[Any]]]
        Original Domain with %(val)s string formatting
    record : Model
        odoo record to get %()s values from
    field_mappers : Dict[str, Union[str, Dict[Any, Any]]]
        dict of {fiel_name:mapper}. where mapper = {source:target}.
        All fields with a mapper will get it's value swapped.
        Usually used to translate relational ids

    Returns
    -------
    Iterable[Union[str, Iterable[Any]]]
        Domain with values from record templated in and mapped according to field mappers
    """
    record.ensure_one()
    out_domain: List[Union[str, Iterable[Any]]] = []
    for subdomain in domain:
        if isinstance(subdomain, str):
            out_domain.append(subdomain)
            continue
        new_out = list(subdomain)

        if isinstance(new_out[2], str):
            if map_template := re.match(r"^%\((.*)\)s$", new_out[2]):
                map_key = map_template.groups()[0]
                mapped_val = mapped_rpc(record, map_key)
                if not mapped_val:
                    new_out[2] = False
                else:
                    try:
                        new_out[2] = map_record_value(mapped_val, record, map_key, field_mappers)
                    except KeyError:
                        new_out[2] = mapped_val
                    if (
                        isinstance(new_out[2], (list, tuple))
                        and len(new_out[2]) == 1
                        and not new_out[1] in ["in", "not in"]
                    ):
                        new_out[2] = new_out[2][0]
                    if isinstance(new_out[2], (datetime.date, datetime.datetime)):
                        new_out[2] = new_out[2].isoformat()
        out_domain.append(new_out)

    return out_domain


def transfer_records_and_map_ids(
    source_model: Model,
    target_model: Model,
    keep_fields: Dict[str, Union[str, Dict[int, int]]],
    match_domain: Iterable[Union[str, Iterable[Any]]],
    source_domain: Optional[Iterable[Union[str, Iterable[Any]]]] = None,
) -> Dict[int, int]:
    """Transfer Records from one odoo instance to another.

    Parameters
    ----------
    source_model : Model
        model where to get records
    target_model : Model
        model where to put records
    keep_fields : Dict[str, Union[str, Dict[int, int]]]
        dict of fields to translate. You can add mappers to translate relational fields
    match_domain : Iterable[Union[str, Iterable[Any]]]
        domain to use for equality matching. Use %(field_name)s syntax to substiture target values.
    source_domain : Optional[Iterable[Union[str, Iterable[Any]]]], optional
        domain to apply to source to not transfer all records, by default None

    Returns
    -------
    Dict[int, int]
        Mapper with new and old IDs
    """
    source_domain = source_domain or []
    source_records = source_model.browse(source_model.search(source_domain))
    mapper = {}
    for index, srec in enumerate(source_records, 1):
        equality_domain = format_domain_values(match_domain, srec, field_mappers=keep_fields)
        trec_id = target_model.search(equality_domain)
        if not trec_id:
            srec_vals = map_record_values(srec, keep_fields)
            for field, action in keep_fields.items():
                if action == "HTML":
                    if not srec_vals[field]:
                        srec_vals[field] = "<p><br></p>"
            trec_id = target_model.create(srec_vals)
            print(f"{index}/{len(source_records)} Created: {srec_vals.get('name') or srec_vals.get('id')}")
        if isinstance(trec_id, (list, tuple)) and len(trec_id) == 1:
            trec_id = trec_id[0]
        mapper[srec.id] = trec_id
    return mapper
