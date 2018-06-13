import pytest


def shell_seg_endcli_test(vrun):
  sha1 = "46f464571edf3c9c5259dfe832be3a06d564f1c5"
  vrun.skip_if_prog_not_available("volumes/sys/l/Shell-Seg", sha1)
  stdin = "endcli\n"
  retcode, stdout, stderr = vrun.run_prog(
      'sys:l/Shell-Seg', vargs=['-x'], stdin=stdin)
  assert retcode == 200
  assert stdout == ["\x0f0.SYS:> PROCESS 0 ENDING"]
  assert stderr == []
