import pytest

def math_single_test(vamos):
  if vamos.flavor in ("sc", "agcc"):
    pytest.skip("math not supported")
  vamos.make_prog("math_single")
  vamos.run_prog_check_data("math_single")
