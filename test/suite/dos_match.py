def dos_match_test(vamos):
    rc, stdout, stderr = vamos.run_prog("dos_match", "sys:")
    assert rc == 0
    assert stdout == [
        "sys: sys: 0 5",
        "c sys:c 0 1",
        "devs sys:devs 0 1",
        "libs sys:libs 0 1",
        "s sys:s 0 1",
        "t sys:t 0 1",
        "sys: sys: 0 9",
    ]
