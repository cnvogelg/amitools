def test_execpy_exec_test(vamos):
    # execute command and set return value
    code = "rc = 42 ; print('hello, world!')"
    retcode, stdout, stderr = vamos.run_prog("test_execpy", "-x", code)
    assert retcode == 42
    assert stdout == ["hello, world!"]
    assert stderr == []


def test_execpy_eval_test(vamos):
    # execute function an use its value as return value
    code = "2 * 21"
    retcode, stdout, stderr = vamos.run_prog("test_execpy", "-e", code)
    assert retcode == 42
    assert stdout == []
    assert stderr == []


def test_execpy_file_test(vamos, tmpdir):
    # execute file
    code = """rc = 42
print('hello, world!')"""
    script_file = tmpdir / "script"
    script_file.write_text(code, "utf-8")
    retcode, stdout, stderr = vamos.run_prog("test_execpy", "-f", str(script_file))
    assert retcode == 42
    assert stdout == ["hello, world!"]
    assert stderr == []


def test_execpy_ctx_func_test(vamos, tmpdir):
    # execute file
    code = """def foobar(ctx):
    print('hello, world!')
    print(type(ctx))
    return 42
"""
    script_file = tmpdir / "script"
    script_file.write_text(code, "utf-8")
    retcode, stdout, stderr = vamos.run_prog(
        "test_execpy", "-c", str(script_file), "foobar"
    )
    assert retcode == 42
    assert stdout == ["hello, world!", "<class 'amitools.vamos.libcore.ctx.LibCtx'>"]
    assert stderr == []


def foobar(ctx):
    """the test ctx_func"""
    print("hello, world!")
    print(type(ctx))
    print(sorted(ctx.__dict__))
    return 42


def test_execpy_vamos_ctx_func_test(vamos):
    # now use the vamos helper to run a function in lib ctx
    retcode, stdout, stderr = vamos.run_ctx_func(foobar)
    assert retcode == 42
    assert stdout == [
        "hello, world!",
        "<class 'amitools.vamos.libcore.ctx.LibCtx'>",
        "['cpu', 'machine', 'mem', 'proxies', 'vlib']",
    ]
    assert stderr == []


def test_execpy_vamos_ctx_func_checked_test(vamos):
    def test(ctx):
        """the nested test ctx_func without return"""
        assert sorted(ctx.__dict__) == ["cpu", "machine", "mem", "proxies", "vlib"]

    vamos.run_ctx_func_checked(test)


def test_execpy_vamos_ctx_func_exec_test(vamos):
    """call exec functions via proxy in ctx func"""

    def test(ctx):
        # get exec lib proxy
        exec = ctx.proxies.get_exec_lib_proxy()
        assert exec
        # call exec functions
        size = 1024
        addr = exec.AllocMem(size, 0)
        assert addr
        exec.FreeMem(addr, size)

    vamos.run_ctx_func_checked(test)


def test_execpy_vamos_ctx_func_dos_test(vamos, tmpdir):
    """call dos functions via proxy in ctx func"""
    sys_file_name = str(tmpdir / "test_file")
    ami_file_name = "root:" + sys_file_name[1:]
    ami_file_len = len(ami_file_name)

    def test(ctx):
        # get dos, exec lib proxy
        exec = ctx.proxies.get_exec_lib_proxy()
        assert exec
        dos = ctx.proxies.get_dos_lib_proxy()
        assert dos
        # allocate name
        name_addr = exec.AllocMem(ami_file_len + 1, 0)
        assert name_addr
        ctx.mem.w_cstr(name_addr, ami_file_name)
        # call dos functions
        fh = dos.Open(name_addr, 1006)
        assert fh
        res = dos.Write(fh, name_addr, ami_file_len)
        assert res == ami_file_len
        # clean up
        dos.Close(fh)
        exec.FreeMem(name_addr, ami_file_len)

    vamos.run_ctx_func_checked(test)
    # check file
    with open(sys_file_name, "r") as fobj:
        data = fobj.read()
        assert data == ami_file_name
