import pytest

def math_double_test(vamos):
  # checked against 38.2
  if vamos.flavor in ("sc", "agcc"):
    pytest.skip("math not supported")
  vamos.make_prog("math_double")
  vamos.run_prog_check_data("math_double")
