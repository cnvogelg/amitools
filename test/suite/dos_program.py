def dos_program_test(vamos):
    rc, stdout, stderr = vamos.run_prog("dos_program")
    assert rc == 0
    assert stdout == ["FFFFFFFF dos_program_" + vamos.flavor, "FFFFFFFF bin"]
