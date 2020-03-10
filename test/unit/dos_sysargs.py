from amitools.vamos.lib.dos.SysArgs import *


def sys_args_ami_quote_test():
    assert ami_quote_str("hello") == '"hello"'
    assert ami_quote_str("") == '""'
    assert ami_quote_str('"') == '"*""'
    assert ami_quote_str("\n\x1b") == '"*N*E"'


def sys_args_to_ami_arg_test():
    # no quoting
    assert sys_arg_to_ami_arg("hello") == "hello"
    # quoted
    assert sys_arg_to_ami_arg("") == '""'
    assert sys_arg_to_ami_arg("hello, world") == '"hello, world"'
    assert sys_arg_to_ami_arg("\n\x1b") == '"*N*E"'
    assert sys_arg_to_ami_arg('"*') == '"*"**"'


def sys_args_to_ami_arg_str_test():
    assert sys_args_to_ami_arg_str([]) == "\n"
    assert sys_args_to_ami_arg_str(["hello"]) == "hello\n"
    assert sys_args_to_ami_arg_str(["hello", "world"]) == "hello world\n"
    assert sys_args_to_ami_arg_str(["", "world"]) == '"" world\n'
    assert sys_args_to_ami_arg_str(["a space", "world"]) == '"a space" world\n'
    assert sys_args_to_ami_arg_str(["\n", "\x1b", '"', "*"]) == '"*N" "*E" "*"" "**"\n'
