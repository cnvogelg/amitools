def test_execpy_exec_test(vamos):
    # execute command and set return value
    code = "rc = 42 ; print('hello, world!')"
    retcode, stdout, stderr = vamos.run_prog("test_execpy", "-x", code)
    assert retcode == 42
    assert stdout == ['hello, world!']
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
    assert stdout == ['hello, world!']
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
    retcode, stdout, stderr = vamos.run_prog("test_execpy", "-c", str(script_file), "foobar")
    assert retcode == 42
    assert stdout == ['hello, world!', "<class 'amitools.vamos.libcore.ctx.LibCtx'>"]
    assert stderr == []


def foobar(ctx):
    """the test ctx_func"""
    print('hello, world!')
    print(type(ctx))
    return 42


def test_execpy_vamos_ctx_func_test(vamos, tmpdir):
    # now use the vamos helper to run a function in lib ctx
    retcode, stdout, stderr = vamos.run_ctx_func(foobar, tmpdir)
    assert retcode == 42
    assert stdout == ['hello, world!', "<class 'amitools.vamos.libcore.ctx.LibCtx'>"]
    assert stderr == []
