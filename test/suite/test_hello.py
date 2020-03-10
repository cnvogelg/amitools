def test_hello_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_hello")
    assert retcode == 0
    assert stdout == ["VamosTest: PrintHello()"]
    assert stderr == []


def test_hello_mem_trace_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_hello", vargs=["-t"])
    assert retcode == 0
    assert stdout == ["VamosTest: PrintHello()"]


def test_hello_mem_int_trace_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_hello", vargs=["-T"])
    assert retcode == 0
    assert stdout == ["VamosTest: PrintHello()"]


def test_hello_instr_trace_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_hello", vargs=["-I"])
    assert retcode == 0
    assert stdout == ["VamosTest: PrintHello()"]


def test_hello_labels_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_hello", vargs=["-B"])
    assert retcode == 0
    assert stdout == ["VamosTest: PrintHello()"]
    assert stderr == []


def test_hello_labels_mem_trace_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_hello", vargs=["-t", "-B"])
    assert retcode == 0
    assert stdout == ["VamosTest: PrintHello()"]


def test_hello_labels_mem_int_trace_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_hello", vargs=["-T", "-B"])
    assert retcode == 0
    assert stdout == ["VamosTest: PrintHello()"]


def test_hello_labels_instr_trace_test(vamos):
    retcode, stdout, stderr = vamos.run_prog("test_hello", vargs=["-I", "-B"])
    assert retcode == 0
    assert stdout == ["VamosTest: PrintHello()"]
