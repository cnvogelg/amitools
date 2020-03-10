class ItemParser:
    """parse items like AmigaDOS splits its argument list"""

    ITEM_EQUAL = -2
    ITEM_ERROR = -1
    ITEM_NOTHING = 0
    ITEM_UNQUOTED = 1
    ITEM_QUOTED = 2

    def __init__(self, csrc, eol_unget_bug=True):
        """set character source csrc that supports getc() and ungetc()"""
        self.csrc = csrc
        self.last_unquoted_char = None
        self.eol_unget_bug = eol_unget_bug

    def read_eol(self):
        """read until end of line"""
        res = []
        if self.last_unquoted_char is not None:
            res.append(self.last_unquoted_char)

        # read until eol
        while True:
            ch = self.csrc.getc()
            if ch in (None, chr(0), "\n", ";"):
                break
            res.append(ch)

        # AmigaOS curiosity:
        # if the last read item was unquoted then remove trailing spaces
        if self.last_unquoted_char is not None:
            while len(res) > 0 and res[-1] in (" ", "\t"):
                res.pop()

        return "".join(res)

    def read_item(self, maxchars):
        """returns (ITEM_*, buf)"""
        null = chr(0)
        self.last_unquoted_char = None

        # skip leading whitespace
        while True:
            ch = self.csrc.getc()
            if ch not in (" ", "\t"):
                break

        # already a terminal char?
        if ch in (None, null, "\n", ";"):
            self.csrc.ungetc()
            return (self.ITEM_NOTHING, None)

        # equal sign?
        if ch == "=":
            return (self.ITEM_EQUAL, None)

        res = []
        status = self.ITEM_NOTHING

        # quoted string?
        if ch == '"':
            while True:
                # no more room?
                if maxchars == 0:
                    res.pop()
                    status = self.ITEM_ERROR
                    break
                # get next char
                maxchars -= 1
                ch = self.csrc.getc()
                # quoted char?
                if ch == "*":
                    ch = self.csrc.getc()
                    # early end?
                    if ch in (None, null, "\n"):
                        status = self.ITEM_ERROR
                        self.csrc.ungetc()
                        break
                    elif ch in ("n", "N"):
                        ch = "\n"
                    elif ch in ("e", "E"):
                        ch = chr(0x1B)
                # early end?
                elif ch in (None, null, "\n"):
                    status = self.ITEM_ERROR
                    self.csrc.ungetc()
                    break
                elif ch == '"':
                    status = self.ITEM_QUOTED
                    break
                res.append(ch)

        # unquoted string
        else:
            # store current char
            if maxchars == 0:
                status = self.ITEM_ERROR
            else:
                maxchars -= 1
                res.append(ch)
                while True:
                    if maxchars == 0:
                        res.pop()
                        status = self.ITEM_ERROR
                        break
                    maxchars -= 1
                    # get next char
                    ch = self.csrc.getc()
                    # terminate
                    if ch in (None, null, "\n"):
                        status = self.ITEM_UNQUOTED
                        if self.eol_unget_bug:
                            self.csrc.ungetc()
                        break
                    elif ch in (" ", "\t", "="):
                        # Know Bug: Don't UNGET for a space or equals sign
                        status = self.ITEM_UNQUOTED
                        self.last_unquoted_char = ch
                        break
                    res.append(ch)

        # build final string
        res_str = "".join(res)
        return status, res_str
