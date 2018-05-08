from amitools.vamos.libnative import LibLoader


def libnative_loader_base_name_test():
  f = LibLoader.get_lib_base_name
  assert f("bla.library") == "bla.library"
  assert f("a/relative/bla.library") == "bla.library"
  assert f("abs:bla.library") == "bla.library"
  assert f("abs:relative/bla.library") == "bla.library"


def libnative_loader_search_paths_test():
  f = LibLoader.get_lib_search_paths
  # abs path
  assert f("progdir:bla.library") == ["progdir:bla.library"]
  assert f("abs:bla.library") == ["abs:bla.library"]
  # rel path
  assert f("bla.library") == ["bla.library",
                              "libs/bla.library",
                              "PROGDIR:bla.library",
                              "PROGDIR:libs/bla.library",
                              "libs:bla.library"]
  assert f("foo/bla.library") == ["foo/bla.library",
                              "libs/foo/bla.library",
                              "PROGDIR:foo/bla.library",
                              "PROGDIR:libs/foo/bla.library",
                              "libs:foo/bla.library"]
