import pytest


def dos_readargs_test(vamos):
    if vamos.flavor == "agcc":
        pytest.skip("needs stdlib")
    vamos.run_prog_checked("dos_readargs")


def dos_readargs2_test(vamos):
    vamos.run_prog_checked("dos_readargs2")


def dos_readargs2_prompt_test(vamos):
    vamos.run_prog_checked("dos_readargs2", "?", stdin="\n")
