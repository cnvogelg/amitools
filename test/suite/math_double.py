
def math_double_test(vamos):
  if vamos.flavor in ("sc", "agcc"):
    return
  vamos.make_prog("math_double")
  vamos.run_prog_check_data("math_double")
