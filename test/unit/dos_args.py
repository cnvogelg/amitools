from amitools.vamos.lib.dos.CSource import CSource
from amitools.vamos.lib.dos.Args import *
from amitools.vamos.lib.dos.Error import *


def template_arg_test():
    # string
    ta = TemplateArg.parse_string("a=b/k")
    assert ta.ktype == TemplateArg.TYPE_STRING
    assert not ta.is_required
    assert ta.is_keyword
    assert not ta.is_multi
    assert ta.keys == ["A", "B"]
    # number
    ta = TemplateArg.parse_string("my=fancy/n")
    assert ta.ktype == TemplateArg.TYPE_NUMBER
    assert not ta.is_required
    assert not ta.is_keyword
    assert not ta.is_multi
    assert ta.keys == ["MY", "FANCY"]
    # switch
    ta = TemplateArg.parse_string("my=fancy/s")
    assert ta.ktype == TemplateArg.TYPE_SWITCH
    assert not ta.is_required
    assert ta.is_keyword
    assert not ta.is_multi
    # toggle
    ta = TemplateArg.parse_string("my=fancy/t")
    assert ta.ktype == TemplateArg.TYPE_TOGGLE
    assert not ta.is_required
    assert ta.is_keyword
    assert not ta.is_multi
    # multi
    ta = TemplateArg.parse_string("my=fancy/m")
    assert ta.ktype == TemplateArg.TYPE_STRING
    assert not ta.is_required
    assert not ta.is_keyword
    assert ta.is_multi
    # full
    ta = TemplateArg.parse_string("my=fancy/f")
    assert ta.ktype == TemplateArg.TYPE_FULL
    assert not ta.is_required
    assert not ta.is_keyword
    assert not ta.is_multi


def template_arg_list_test():
    tal = TemplateArgList.parse_string("a=b/k,all/m")
    assert tal.len() == 2
    assert tal.get_arg(0).pos == 0
    assert tal.get_arg(1).pos == 1
    assert tal.get_arg(2) is None
    assert tal.get_arg(-1) is None
    assert tal.find_arg("a").pos == 0
    assert tal.find_arg("ALL").pos == 1
    assert tal.find_arg("blob") is None


class DummyAccess:
    def __init__(self):
        self.result = []

    def w32(self, addr, val):
        val &= 0xFFFFFFFF
        self.result.append("%08x:w32:%08x" % (addr, val))

    def r32(self, addr):
        return 0

    def w_cstr(self, addr, s):
        self.result.append("%08x:w_cstr:%s" % (addr, s))

    def assert_w32s(self, addr, *vals):
        for v in vals:
            v &= 0xFFFFFFFF
            s = "%08x:w32:%08x" % (addr, v)
            assert s in self.result
            addr += 4

    def assert_w_cstrs(self, addr, *vals):
        for v in vals:
            s = "%08x:w_cstr:%s" % (addr, v)
            assert s in self.result
            addr += len(v) + 1

    def dump(self):
        for r in sorted(self.result):
            print(r)


def result_list_test():
    tal = TemplateArgList.parse_string("switch/s,toggle/t,multi/m,string,number/n")
    print(tal)
    rl = ParseResultList(tal)
    assert rl.len == tal.len()
    # fill in fake result
    a = "hello"
    b = "world"
    c = "huhu"
    la = len(a)
    lb = len(b)
    lc = len(c)
    rl.set_result(0, True)
    rl.set_result(1, True)
    rl.set_result(2, [a, b])
    rl.set_result(3, c)
    rl.set_result(4, 42)
    # calc byte size
    exp_bytes = la + lb + lc + 3
    exp_longs = 1 + 3
    exp_bytes += exp_longs * 4
    num_bytes, num_longs = rl.calc_extra_result_size()
    assert num_bytes == exp_bytes
    assert num_longs == exp_longs
    # generate output
    da = DummyAccess()
    array_ptr = 0x1000
    extra_ptr = 0x2000
    extra_bptr = extra_ptr + num_longs * 4
    rl.generate_result(da, array_ptr, extra_ptr, num_longs)
    # check output
    da.dump()
    pa = extra_bptr
    pb = extra_bptr + la + 1
    pc = extra_bptr + la + lb + 2
    da.assert_w32s(array_ptr, -1, -1, extra_ptr, pc)
    da.assert_w32s(extra_ptr, pa, pb, 0, 42)
    da.assert_w_cstrs(extra_bptr, a, b, c)


def result_list2_test():
    tal = TemplateArgList.parse_string("multi/m/n,full/f")
    print(tal)
    rl = ParseResultList(tal)
    assert rl.len == tal.len()
    # fill in fake result
    a = "hello"
    la = len(a)
    rl.set_result(0, [23, 42])
    rl.set_result(1, a)
    # calc byte size
    exp_bytes = la + 1
    exp_longs = 3 + 2
    exp_bytes += exp_longs * 4
    num_bytes, num_longs = rl.calc_extra_result_size()
    assert num_bytes == exp_bytes
    assert num_longs == exp_longs
    # generate output
    da = DummyAccess()
    array_ptr = 0x1000
    extra_ptr = 0x2000
    extra_bptr = extra_ptr + num_longs * 4
    rl.generate_result(da, array_ptr, extra_ptr, num_longs)
    # check output
    da.dump()
    pa = extra_bptr
    da.assert_w32s(array_ptr, extra_ptr + 8, pa)
    da.assert_w32s(extra_ptr, 23, 42, extra_ptr, extra_ptr + 4, 0)
    da.assert_w_cstrs(extra_bptr, a)


def check_parse_args(template, in_str, exp_res_list=None, error=NO_ERROR):
    tal = TemplateArgList.parse_string(template)
    assert tal is not None
    p = ArgsParser(tal)
    data = (in_str + "\n").encode("latin-1")
    csrc = CSource(data)
    result = p.parse(csrc)
    print(dos_error_strings[result])
    assert result == error
    if error == NO_ERROR:
        assert p.get_result_list().get_results() == exp_res_list


def parse_args_basic_test():
    # string
    check_parse_args("AKEY", "hello", ["hello"])
    # number
    check_parse_args("AKEY/N", "123", [123])
    check_parse_args("AKEY/N", "hello", error=ERROR_BAD_NUMBER)
    check_parse_args("AKEY/N", "-1", error=ERROR_BAD_NUMBER)
    # switch/toggle
    check_parse_args("AKEY/S", "akey", [True])
    check_parse_args("AKEY/T", "akey", [True])
    check_parse_args("AKEY/S", "key", error=ERROR_TOO_MANY_ARGS)
    check_parse_args("AKEY/T", "key", error=ERROR_TOO_MANY_ARGS)
    # full
    check_parse_args("AKEY/F", "hello world", ["hello world"])
    # multi string
    check_parse_args("MULTI/M", "hello world", [["hello", "world"]])
    check_parse_args("MULTI/M", "", [None])
    # multi number
    check_parse_args("MULTI/M/N", "23 42", [[23, 42]])
    check_parse_args("MULTI/M/N", "", [None])
    check_parse_args("MULTI/M/N", "23 hu", error=ERROR_BAD_NUMBER)


def parse_args_keyword_test():
    # not set
    check_parse_args("AKEY", "", [None])
    # regular use
    check_parse_args("AKEY", "akey hello", ["hello"])
    check_parse_args("AKEY", "akey=hello", ["hello"])
    # quoted string is accepted as value
    check_parse_args("AKEY", '"akey"', ["akey"])
    # if key is given then it needs a value
    check_parse_args("AKEY", "akey", error=ERROR_KEY_NEEDS_ARG)
    # keyword required
    check_parse_args("AKEY/K", "akey hello", ["hello"])
    check_parse_args("AKEY/K", "akey=hello", ["hello"])
    # keyword must be present
    check_parse_args("AKEY/K", "hello", error=ERROR_TOO_MANY_ARGS)


def parse_args_required_test():
    # must be set
    check_parse_args("AKEY/A", "", error=ERROR_REQUIRED_ARG_MISSING)


def parse_args_multi_test():
    check_parse_args("MULTI/M,AKEY", "hello", [["hello"], None])
    # /M munges all
    check_parse_args("MULTI/M,AKEY", "a b", [["a", "b"], None])
    # but a key can fetch it
    check_parse_args("MULTI/M,AKEY", "akey a b", [["b"], "a"])
    # or if key is required
    check_parse_args("MULTI/M,AKEY/A", "a b", [["a"], "b"])
    # forced multi
    check_parse_args("AKEY/A,MULTI/M/A,BKEY/A", "a b c", ["a", ["b"], "c"])
    check_parse_args(
        "AKEY/A,BKEY/A,MULTI/M/A,CKEY/A,DKEY/A",
        "a b c d e",
        ["a", "b", ["c"], "d", "e"],
    )
