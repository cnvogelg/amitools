def pytask_dos_split_name_test(vamos_task):
    def proc(ctx, task):
        dos_proxy = ctx.proxies.get_dos_lib_proxy()

        name = ctx.alloc.alloc_cstr("ab/cd")
        buf = ctx.alloc.alloc_memory(8, label="split name buffer")

        # first part up to the separator
        assert dos_proxy.SplitName(name.addr, ord("/"), buf.addr, 0, 8) == 3
        assert ctx.mem.r_cstr(buf.addr) == "ab"

        # last part: no separator left
        assert dos_proxy.SplitName(name.addr, ord("/"), buf.addr, 3, 8) == 0xFFFFFFFF
        assert ctx.mem.r_cstr(buf.addr) == "cd"

        # only size - 1 characters plus NUL are copied
        assert dos_proxy.SplitName(name.addr, ord("/"), buf.addr, 0, 2) == 0xFFFFFFFF
        assert ctx.mem.r_cstr(buf.addr) == "a"

        # a name without separator is a single last part
        no_sep = ctx.alloc.alloc_cstr("abcd")
        assert dos_proxy.SplitName(no_sep.addr, ord("/"), buf.addr, 0, 8) == 0xFFFFFFFF
        assert ctx.mem.r_cstr(buf.addr) == "abcd"

        ctx.alloc.free_memory(buf)
        ctx.alloc.free_cstr(no_sep)
        ctx.alloc.free_cstr(name)
        return 0

    exit_codes = vamos_task.run([proc], process=True)
    assert exit_codes == [0]
