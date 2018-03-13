import pytest

def dos_readargs_test(vamos):
  if vamos.flavor == "agcc":
    pytest.skip("needs stdlib")
  vamos.make_prog("dos_readargs")
  vamos.run_prog_checked("dos_readargs")
