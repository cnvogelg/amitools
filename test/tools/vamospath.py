import os


def vamospath_ami2sys_cwd_test(toolrun):
  cwd = os.getcwd()
  status, out, err = toolrun.run("vamospath", "ami2sys", "")
  assert status == 0
  assert err == []
  assert out == [cwd]


def vamospath_sys2ami_cwd_test(toolrun):
  cwd = os.getcwd()
  status, out, err = toolrun.run("vamospath", "sys2ami", cwd)
  assert status == 0
  assert err == []
  assert out == ["sys:"]
