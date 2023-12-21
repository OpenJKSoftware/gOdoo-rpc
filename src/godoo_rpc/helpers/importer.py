"""Helper Methods for Odoo."""

from odoorpc import ODOO


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
