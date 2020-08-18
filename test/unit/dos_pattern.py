from amitools.vamos.lib.dos.PatternMatch import (
    pattern_parse,
    pattern_match,
    pattern_dump,
)


def pattern_simple_test():
    pat = pattern_parse("test.o")
    assert pattern_match(pat, "test.o")
    assert pattern_match(pat, "TEST.o")
    assert not pattern_match(pat, "testo.o")


def pattern_simple_with_case_test():
    pat = pattern_parse("test.o", ignore_case=False)
    print(pat)
    assert pattern_match(pat, "test.o")
    assert not pattern_match(pat, "TEST.o")
    assert not pattern_match(pat, "testo.o")


def pattern_any_test():
    pat = pattern_parse("#?")
    assert pattern_match(pat, "bla")
    pat = pattern_parse("#?.o")
    assert pattern_match(pat, "bla.o")
    assert not pattern_match(pat, "bla")


def pattern_not_test():
    pat = pattern_parse("~(test.o)")
    assert pattern_match(pat, "bla")
    assert not pattern_match(pat, "test.o")


def pattern_not_any_test():
    pat = pattern_parse("~(#?.o)")
    assert pattern_match(pat, "bla")
    assert not pattern_match(pat, "test.o", True)
