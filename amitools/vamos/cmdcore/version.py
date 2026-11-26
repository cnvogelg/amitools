"""amitools version lookup for the internal ``vamos`` command."""

from importlib.metadata import PackageNotFoundError, version

#: fallback for a non-installed (source checkout) amitools
UNKNOWN_VERSION = "unknown"


def get_amitools_version():
    """return the installed amitools version or a fallback string"""
    try:
        return version("amitools")
    except PackageNotFoundError:
        return UNKNOWN_VERSION
