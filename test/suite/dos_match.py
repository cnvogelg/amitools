
def dos_match_test(vamos):
  rc, stdout, stderr = vamos.run_prog("dos_match", "sys:")
  assert rc == 0
  assert stdout == [
    "sys: sys: 0",
    "c sys:c 0",
    "devs sys:devs 0",
    "l sys:l 0",
    "libs sys:libs 0",
    "s sys:s 0"
  ]
