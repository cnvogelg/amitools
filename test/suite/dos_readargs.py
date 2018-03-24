import pytest

def dos_readargs_test(vamos):
  if vamos.flavor == "agcc":
    pytest.skip("needs stdlib")
  vamos.run_prog_checked("dos_readargs")
