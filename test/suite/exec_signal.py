def exec_signal_test(vamos):
    rc, stdout, stderr = vamos.run_prog("exec_signal")
    assert rc == 24
