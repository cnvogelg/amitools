import os


def vamostool_path_ami2sys_cwd_test(toolrun):
  cwd = os.getcwd()
  status, out, err = toolrun.run("vamostool", "path", "ami2sys", "")
  assert status == 0
  assert err == []
  assert out == [cwd]


def vamostool_path_ami2sys_error_test(toolrun):
  status, out, err = toolrun.run("vamostool", "-Vcwd:.", "path", "ami2sys", "/")
  assert status == 1
  assert err == ["path='cwd:': can't join parent relative path"]
  assert out == []


def vamostool_path_sys2ami_cwd_test(toolrun):
  cwd = os.getcwd()
  status, out, err = toolrun.run("vamostool", "-Vcwd:.", "path", "sys2ami", cwd)
  assert status == 0
  assert err == []
  assert out == ["cwd:"]


def vamostool_path_sys2ami_tmp_test(toolrun, tmpdir):
  p = str(tmpdir)
  status, out, err = toolrun.run("vamostool", "path", "sys2ami", p)
  assert status == 0
  assert err == []
  assert out == ["root:" + p[1:]]


def vamostool_type_list_test(toolrun):
  status, out, err = toolrun.run("vamostool", "type", "list")
  assert status == 0
  assert err == []
  assert "ExecLibrary" in out
