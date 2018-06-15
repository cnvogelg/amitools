from amitools.vamos.cfgcore import ConfigDict


def cfgcore_cfgdict_test():
  rd = ConfigDict({
      'a': 10,
      'b': 20
  })
  assert rd.a == 10
  assert rd.b == 20
  rd.a = 'hello'
  assert rd.a == 'hello'
  assert rd['a'] == 'hello'
  del rd.b
  assert rd == {
    'a': 'hello'
  }
