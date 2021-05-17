def typetool_list_test(toolrun):
    status, out, err = toolrun.run("typetool", "list")
    assert status == 0
    assert err == []
    assert "ExecLibrary" in out


def typetool_dump_test(toolrun):
    status, out, err = toolrun.run("typetool", "dump", "ExecLibrary")
    assert status == 0
    assert err == []
    assert "ExecLibrary" in out[0]


def typetool_lookup_test(toolrun):
    status, out, err = toolrun.run(
        "typetool", "lookup", "ExecLibrary", "ex_MemHandlers.mlh_Tail"
    )
    assert status == 0
    assert err == []
    assert "ExecLibrary" in out[0]
    assert "ex_MemHandlers" in out[1]
    assert "mlh_Tail" in out[2]


def typetool_offset_test(toolrun):
    status, out, err = toolrun.run("typetool", "offset", "ExecLibrary", "622")
    assert status == 0
    assert err == []
    assert "ExecLibrary" in out[0]
    assert "ex_MemHandlers" in out[1]
    assert "mlh_Tail" in out[2]
