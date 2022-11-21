"""gOdoo-rpc."""
__version__ = "0.0.1"
from . import odoo2odoo_mapper  # noqa
from .api import OdooApiWrapper  # noqa
from .file_2_odoo import import_data, import_dataset  # noqa
from .login import login_odoo, login_odoo_env  # noqa
from .odoo_dataset import OdooDataset  # noqa
