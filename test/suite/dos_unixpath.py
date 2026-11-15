import pytest


def dos_unixpath_test(vamos):
    """libnix rewrites "." and ".." into the AmigaDOS parent step, which
    vamos must resolve anywhere in a path; the other runtimes do not
    rewrite paths and their binary only returns 0"""
    if vamos.flavor != "gcc":
        pytest.skip("needs libnix")
    vamos.run_prog_checked("dos_unixpath")
