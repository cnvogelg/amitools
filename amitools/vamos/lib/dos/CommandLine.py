from .Item import ItemParser
from .CSource import CSource


class CommandLine:
    """parse a string like the Amiga shell would do"""

    LINE_OK = 0
    COMMAND_ERROR = 1
    PREMATURE_END = 2
    REDIR_IN_FAILED = 3
    REDIR_OUT_FAILED = 4
    MULTI_REDIR_IN = 5
    MULTI_REDIR_OUT = 6

    def __init__(self):
        self._reset()

    def __str__(self):
        return "[cmd=%s, arg_str=%s, in=%s, out=%s, append=%s]" % (
            self.cmd,
            self.arg_str,
            self.redir_in,
            self.redir_out,
            self.append_out,
        )

    def _reset(self):
        self.cmd = None
        self.arg_str = None
        self.redir_in = None
        self.redir_out = None
        self.append_out = False

    def get_cmd(self):
        """get command part of line. quoted commands are unquoted"""
        return self.cmd

    def get_arg_str(self):
        """get argument str of line with terminating newline"""
        return self.arg_str

    def get_redir_in(self):
        """get redirection if any or None. redir is unquoted"""
        return self.redir_in

    def get_redir_out(self):
        """get redirection if any or None. redir is unquoted"""
        return self.redir_out

    def is_append_out(self):
        """True if output redirection shall append"""
        return self.append_out

    def parse_line(self, line):
        self._reset()
        max_char = 512
        csrc = CSource(line.encode("latin-1"))

        # read command
        parser = ItemParser(csrc, False)
        status, self.cmd = parser.read_item(max_char)
        if status not in (ItemParser.ITEM_QUOTED, ItemParser.ITEM_UNQUOTED):
            return self.COMMAND_ERROR

        # read arg str
        quoted = False
        arg_res = []
        while True:
            ch = csrc.getc()
            if quoted:
                if ch == '"':  # end quote
                    quoted = False
                if ch in (None, "\n"):
                    # error: premature end
                    return self.PREMATURE_END
                arg_res.append(ch)
            else:
                if ch in (None, "\n", "*"):
                    break
                elif ch == '"':  # quoting
                    quoted = True
                    arg_res.append(ch)
                elif ch == "<":  # redir in?
                    if self.redir_in is not None:
                        return self.MULTI_REDIR_IN
                    status, self.redir_in = parser.read_item(max_char)
                    if status not in (ItemParser.ITEM_QUOTED, ItemParser.ITEM_UNQUOTED):
                        return self.REDIR_IN_FAILED
                elif ch == ">":  # redir out?
                    if self.redir_out is not None:
                        return self.MULTI_REDIR_OUT
                    next_ch = csrc.getc()
                    if next_ch == ">":
                        self.append_out = True
                    else:
                        csrc.ungetc()
                    status, self.redir_out = parser.read_item(max_char)
                    if status not in (ItemParser.ITEM_QUOTED, ItemParser.ITEM_UNQUOTED):
                        return self.REDIR_OUT_FAILED
                else:
                    arg_res.append(ch)
        # append final newline
        if len(arg_res) == 0 or arg_res[-1] != "\n":
            arg_res.append("\n")
        # rebuild arg str
        self.arg_str = "".join(arg_res)
        return self.LINE_OK
