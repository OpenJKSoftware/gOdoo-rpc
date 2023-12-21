"""Handle Shell Environment."""
import os


def ensure_env_var(var_name: str) -> str:
    """Load an environment variable as string.

    Parameters
    ----------
    var_name : str
        env name

    Returns
    -------
    str
        the env var, empty string of empty

    Raises
    ------
    LookupError
        if the env variable doesnt exist
    """
    var = os.getenv(var_name)
    if not var:
        raise LookupError(f'Missing env Variable "{var_name}"')
    return str(var)
