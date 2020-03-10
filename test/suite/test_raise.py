def test_raise_invalid_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_raise", "bla")
    assert retcode == 0
    assert stdout == ["VamosTest: Invalid Error: bla"]
    assert stderr == []


def test_raise_runtime_error_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_raise", "RuntimeError")
    assert retcode == 1
    assert stdout == ["VamosTest: raise RuntimeError"]
    assert stderr[0] == "   machine:  ERROR:  ----- ERROR in CPU Run #1 -----"
    assert stderr[-1] == "      main:  ERROR:  vamos failed!"


def test_raise_vamos_internal_error_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_raise", "VamosInternalError")
    assert retcode == 1
    assert stdout == ["VamosTest: raise VamosInternalError"]
    assert stderr[0] == "   machine:  ERROR:  ----- ERROR in CPU Run #1 -----"
    assert stderr[-1] == "      main:  ERROR:  vamos failed!"
    assert "VamosInternalError: Internal Vamos Error: VamosTest" in "\n".join(stderr)


def test_raise_invalid_memory_access_error_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_raise", "InvalidMemoryAccessError")
    assert retcode == 1
    assert stdout == ["VamosTest: raise InvalidMemoryAccessError"]
    assert stderr[0] == "   machine:  ERROR:  ----- ERROR in CPU Run #1 -----"
    assert stderr[-1] == "      main:  ERROR:  vamos failed!"
    assert "InvalidMemoryAccessError: Invalid Memory Access R(4): 000200" in "\n".join(
        stderr
    )
