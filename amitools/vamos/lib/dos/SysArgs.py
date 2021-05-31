special_chars = (" ", '"', "*", "\n", "\x1b")


def ami_quote_str(chars):
    """perform Amiga-like shell quoting with surrounding "..." quotes
    an special chars quoted with asterisk *
    """
    if chars == "":
        return '""'
    res = ['"']
    for c in chars:
        if c == "\n":
            res.append("*N")
        elif c == "\x1b":  # ESCAPE
            res.append("*E")
        elif c == "*":
            res.append("**")
        elif c == '"':
            res.append('*"')
        else:
            res.append(c)
    res.append('"')
    return "".join(res)


def sys_arg_to_ami_arg(sys_arg):
    # quote empty string
    if sys_arg == "":
        return '""'
    # check if quoting is needed
    quote = False
    for sc in special_chars:
        if sc in sys_arg:
            quote = True
            break
    if quote:
        return ami_quote_str(sys_arg)
    else:
        return sys_arg


def sys_args_to_ami_arg_str(sys_args):
    """convert a regular argv[] array of your host system to a single
    string used as an Amiga argument

    this function handles automatic quoting if necessary and
    also appends a final newline
    """
    ami_args = []
    for sys_arg in sys_args:
        ami_arg = sys_arg_to_ami_arg(sys_arg)
        ami_args.append(ami_arg)
    arg_str = " ".join(ami_args) + "\n"
    return arg_str
