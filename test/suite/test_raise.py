
def test_raise_invalid_test(vamos):
  vamos.make_prog("test_raise")
  retcode, stdout, stderr = vamos.run_prog("test_raise", "bla")
  assert retcode == 0
  assert stdout == ["VamosTest: Invalid Error: bla"]
  assert stderr == []

def test_raise_runtime_error_test(vamos):
  vamos.make_prog("test_raise")
  retcode, stdout, stderr = vamos.run_prog("test_raise", "RuntimeError")
  assert retcode == 1
  assert stdout == ["VamosTest: raise RuntimeError"]
  assert stderr[0] == "Traceback (most recent call last):"
  assert stderr[-1] == "RuntimeError: VamosTest"

def test_raise_vamos_internal_error_test(vamos):
  vamos.make_prog("test_raise")
  retcode, stdout, stderr = vamos.run_prog("test_raise", "VamosInternalError")
  assert retcode == 1
  assert stdout == ["VamosTest: raise VamosInternalError"]
  assert stderr[0] == '      main:  ERROR:  Traceback (most recent call last):'
  assert '      main:  ERROR:  VamosInternalError: Internal Vamos Error: VamosTest' in stderr

def test_raise_invalid_memory_access_error_test(vamos):
  vamos.make_prog("test_raise")
  retcode, stdout, stderr = vamos.run_prog("test_raise", "InvalidMemoryAccessError")
  assert retcode == 1
  assert stdout == ["VamosTest: raise InvalidMemoryAccessError"]
  assert stderr[0] == '      main:  ERROR:  Traceback (most recent call last):'
  assert '      main:  ERROR:  InvalidMemoryAccessError: Invalid Memory Access R(4): 000200' in stderr
