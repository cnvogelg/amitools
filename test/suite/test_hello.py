
def test_hello_test(vamos):
  vamos.make_prog("test_hello")
  retcode, stdout = vamos.run_prog("test_hello")
  assert retcode == 0
  assert stdout == ["VamosTest: PrintHello()"]
