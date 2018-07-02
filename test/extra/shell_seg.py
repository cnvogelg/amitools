import pytest


def check_shell_seg(vrun):
  sha1 = "46f464571edf3c9c5259dfe832be3a06d564f1c5"
  vrun.skip_if_prog_not_available("volumes/sys/l/Shell-Seg", sha1)


def shell_seg_endcli_test(vrun):
  check_shell_seg(vrun)
  stdin = "endcli\n"
  retcode, stdout, stderr = vrun.run_prog(
      'sys:l/Shell-Seg', vargs=['-x'], stdin=stdin)
  assert retcode == 200
  assert stdout == ["\x0f0.SYS:> PROCESS 0 ENDING"]
  assert stderr == []


def shell_seg_proc_args_test(vrun, vamos):
  check_shell_seg(vrun)
  vamos.make_prog("proc_args")
  cmd_name = vamos.get_prog_bin_name("proc_args")
  stdin = cmd_name + "\nendcli\n"
  retcode, stdout, stderr = vrun.run_prog(
      'sys:l/Shell-Seg', vargs=['-x'], stdin=stdin)
  assert retcode == 200
  assert stdout == [
      '\x0f0.SYS:> a0:NULL',
      'in:"\\n"',
      '\x0f0.SYS:> PROCESS 0 ENDING'
  ]
  assert stderr == []


def shell_seg_run_proc_args_test(vrun, vamos):
  check_shell_seg(vrun)
  vamos.make_prog("proc_args")
  cmd_name = vamos.get_prog_bin_name("proc_args")
  stdin = "run " + cmd_name + "\nendcli\n"
  retcode, stdout, stderr = vrun.run_prog(
      'sys:l/Shell-Seg', vargs=['-x'], stdin=stdin)
  assert retcode == 200
  assert stdout == [
      "\x0f0.SYS:> \x0f0.SYS:> PROCESS 0 ENDING"
  ]
  assert stderr == []
