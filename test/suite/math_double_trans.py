
def math_double_trans_test(vamos):
  if vamos.flavor in ("sc", "agcc"):
    return
  vamos.make_prog("math_double_trans")
  vamos.run_prog_check_data("math_double_trans")
