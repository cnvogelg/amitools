from amitools.vamos.lib.dos.CommandLine import CommandLine


def dos_cmdline_cmd_test():
    cl = CommandLine()
    # no command given
    assert cl.parse_line("") == cl.COMMAND_ERROR
    assert cl.parse_line('"open_quote') == cl.COMMAND_ERROR
    # ok command
    assert cl.parse_line("cmd") == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_arg_str() == "\n"
    # command gets automatically unquoted
    assert cl.parse_line('"a cmd"') == cl.LINE_OK
    assert cl.get_cmd() == "a cmd"
    assert cl.get_arg_str() == "\n"


def dos_cmdline_args_test():
    cl = CommandLine()
    # some args
    assert cl.parse_line('cmd some "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_arg_str() == 'some "args" and "more"\n'


def dos_cmdline_redir_in_test():
    cl = CommandLine()
    # redir in
    assert cl.parse_line('cmd <in some "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_in() == "in"
    assert cl.get_arg_str() == 'some "args" and "more"\n'
    # redir in 2
    assert cl.parse_line('cmd some <in "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_in() == "in"
    assert cl.get_arg_str() == 'some "args" and "more"\n'
    # redir in quoting
    assert cl.parse_line('cmd <"in redir" some "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_in() == "in redir"
    assert cl.get_arg_str() == ' some "args" and "more"\n'
    # redir in quoting 2
    assert cl.parse_line('cmd some <"in redir" "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_in() == "in redir"
    assert cl.get_arg_str() == 'some  "args" and "more"\n'
    # redir in quoting 3
    assert cl.parse_line('cmd some <"in redir""args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_in() == "in redir"
    assert cl.get_arg_str() == 'some "args" and "more"\n'


def dos_cmdline_redir_out_test():
    cl = CommandLine()
    # redir out
    assert cl.parse_line('cmd >out some "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out"
    assert not cl.is_append_out()
    assert cl.get_arg_str() == 'some "args" and "more"\n'
    # redir out 2
    assert cl.parse_line('cmd some >out "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out"
    assert not cl.is_append_out()
    assert cl.get_arg_str() == 'some "args" and "more"\n'
    # redir out quoting
    assert cl.parse_line('cmd >"out redir" some "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out redir"
    assert not cl.is_append_out()
    assert cl.get_arg_str() == ' some "args" and "more"\n'
    # redir out quoting 2
    assert cl.parse_line('cmd some >"out redir" "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out redir"
    assert not cl.is_append_out()
    assert cl.get_arg_str() == 'some  "args" and "more"\n'
    # redir out quoting 3
    assert cl.parse_line('cmd some >"out redir""args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out redir"
    assert not cl.is_append_out()
    assert cl.get_arg_str() == 'some "args" and "more"\n'


def dos_cmdline_redir_append_test():
    cl = CommandLine()
    # redir out
    assert cl.parse_line('cmd >>out some "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out"
    assert cl.is_append_out()
    assert cl.get_arg_str() == 'some "args" and "more"\n'
    # redir out 2
    assert cl.parse_line('cmd some >>out "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out"
    assert cl.is_append_out()
    assert cl.get_arg_str() == 'some "args" and "more"\n'
    # redir out quoting
    assert cl.parse_line('cmd >>"out redir" some "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out redir"
    assert cl.is_append_out()
    assert cl.get_arg_str() == ' some "args" and "more"\n'
    # redir out quoting 2
    assert cl.parse_line('cmd some >>"out redir" "args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out redir"
    assert cl.is_append_out()
    assert cl.get_arg_str() == 'some  "args" and "more"\n'
    # redir out quoting 3
    assert cl.parse_line('cmd some >>"out redir""args" and "more"') == cl.LINE_OK
    assert cl.get_cmd() == "cmd"
    assert cl.get_redir_out() == "out redir"
    assert cl.is_append_out()
    assert cl.get_arg_str() == 'some "args" and "more"\n'
