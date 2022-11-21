"""Provides the Odoo Session."""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from urllib.parse import urlparse

import odoorpc
import requests
from dotenv import load_dotenv
from j_pandas_datalib import ensure_env_var

from .api import OdooApiWrapper

logger = logging.getLogger(__name__)


def wait_for_odoo(
    odoo_host: str, odoo_db: str, odoo_user: str, odoo_password: str, timeout_seconds: int = 600
) -> OdooApiWrapper:
    """Wait for Odoo Connection.

    Parameters
    ----------
    odoo_host : str
    odoo_db : str
    odoo_user : str
    odoo_password : str
    timeout_seconds : int, optional
        timeout to wait before raising, by default 600

    Returns
    -------
    OdooApiWrapper

    Raises
    ------
    TimeoutError
        If login timeout exeeded
    """
    start_time = datetime.now()
    while True:
        try:
            odoo_api = login_odoo(
                odoo_host=odoo_host,
                odoo_db=odoo_db,
                odoo_user=odoo_user,
                odoo_password=odoo_password,
            )
            return OdooApiWrapper(odoo_api)
        except (requests.HTTPError, requests.ConnectionError):
            sleep(1)
        if datetime.now() - timedelta(minutes=timeout_seconds) >= start_time:
            raise TimeoutError(f"Could not reach odoo after timeout of {timeout_seconds} seconds")


def login_odoo(
    odoo_host: str,
    odoo_db: str,
    odoo_user: str,
    odoo_password: str,
) -> odoorpc.ODOO:
    """Make sure ODOO RPC is connected and authenticated.

    Parameters
    ----------
    odoo_host : str
        Url to Odoo
    odoo_db : str
        odoo db name
    odoo_user : str
        login user
    odoo_password : str
        login password

    Returns
    -------
    odoorpc.ODOO
        odoo  rpc session

    Raises
    ------
    LookupError
        When db could not be found in Odoo
    """
    myurl = urlparse(odoo_host, allow_fragments=True)

    requests.head(myurl.geturl(), timeout=1200).raise_for_status()
    port = myurl.port or 80
    if port == 80 and myurl.scheme == "https":
        port = 443
    logger.info("Connecting to Odoo instance on: %s:%s", myurl.hostname, port)

    rpc_session = odoorpc.ODOO(
        host=myurl.hostname,
        port=port,
        timeout=300,
        protocol="jsonrpc+ssl" if myurl.scheme == "https" else "jsonrpc",
    )

    logger.debug(
        "Logging Into Odoo DB=%s, User=%s Password=%s",
        odoo_db,
        odoo_user,
        "*" * len(odoo_password),
    )
    rpc_session.login(odoo_db, odoo_user, odoo_password)
    return rpc_session


def login_odoo_env(dotenv_path: str = ".env", override_env: bool = False) -> odoorpc.ODOO:
    """Log into Odoo using Env Vars.

    Parameters
    ----------
    dotenv_path : str, optional
        Path to .env file, by default ".env"
    override_env : bool, optional
        Wether to override existing env variables with .env, by default False

    Returns
    -------
    OdooApiWrapper
        Logged in Odoo API
    """
    if Path(dotenv_path).exists():
        load_dotenv(dotenv_path, override=override_env)
    return login_odoo(
        odoo_host=ensure_env_var("ODOO_HOST"),
        odoo_db=ensure_env_var("ODOO_DB"),
        odoo_user=ensure_env_var("ODOO_USER"),
        odoo_password=ensure_env_var("ODOO_PASSWORD"),
    )
