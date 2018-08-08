def typetool_list_test(toolrun):
  status, out, err = toolrun.run("typetool", "list")
  assert status == 0
  assert err == []
  assert "ExecLibrary" in out
