import pytest


def check_arg(vamos, args, arg_res):
    # vc currently mangles GetArgStr()
    if vamos.flavor == "vc":
        eol = ""
    else:
        eol = "\\n"
    stdout, stderr = vamos.run_prog_checked("proc_args", *args)
    assert stdout[0] == 'a0:"' + arg_res + eol + '"'
    assert stdout[1] == 'in:"' + arg_res + '\\n"'
    assert stderr == []


def proc_args_test(vamos):
    check_arg(vamos, [], "")
