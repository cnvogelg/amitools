# pattern match constants
P_ANY = 0x80
P_SINGLE = 0x81
P_ORSTART = 0x82
P_ORNEXT = 0x83
P_OREND = 0x84
P_NOT = 0x85
P_NOTEND = 0x86
P_NOTCLASS = 0x87
P_CLASS = 0x88
P_REPBEG = 0x89
P_REPEND = 0x8A
P_STOP = 0x8B

p_txt = {
    P_ANY: "P_ANY",
    P_SINGLE: "P_SINGLE",
    P_ORSTART: "P_ORSTART",
    P_ORNEXT: "P_ORNEXT",
    P_OREND: "P_OREND",
    P_NOT: "P_NOT",
    P_NOTEND: "P_NOTEND",
    P_NOTCLASS: "P_NOTCLASS",
    P_CLASS: "P_CLASS",
    P_REPBEG: "P_REPBEG",
    P_REPEND: "P_REPEND",
    P_STOP: "P_STOP",
}


class Pattern:
    def __init__(self, src_str, pat_str, ignore_case, has_wildcard):
        self.src_str = src_str
        self.pat_str = pat_str
        self.ignore_case = ignore_case
        self.has_wildcard = has_wildcard

    def __str__(self):
        return "[src='%s'->pat='%s',ignore_case=%s,has_wildcard=%s]" % (
            self.src_str,
            self.pat_str,
            self.ignore_case,
            self.has_wildcard,
        )


def _pop_non_or(blocks, dst):
    while True:
        if len(blocks) == 0:
            return dst
        if blocks[-1] != P_OREND:
            p = blocks.pop()
            dst += chr(p)
        else:
            return dst


def pattern_parse(src_str, ignore_case=True, star_is_wild=False):
    """tokenize pattern. return tokenized pattern or None if an error occurred"""
    dst = ""
    n_src = len(src_str)

    has_wild = False
    blocks = []
    flush_blocks = False

    if ignore_case:
        tr = lambda x: x.lower()
    else:
        tr = lambda x: x

    pos = 0
    while pos < n_src:
        flush_blocks = True

        # current char and next one (if available)
        src = src_str[pos]
        if pos != n_src - 1:
            next = src_str[pos + 1]
        else:
            next = None

        # '#' - match following block/char 0 or more times
        if src == "#":
            has_wild = True
            # next char?
            if next == None:
                return None
            # '#?' - match any characters
            if next == "?":
                dst += chr(P_ANY)
                pos += 1
            # invalid
            elif next == ")":
                return None
            # begin REP block
            else:
                dst += chr(P_REPBEG)
                blocks.append(P_REPEND)
                flush_blocks = False

        # '~' - negate following expression
        elif src == "~":
            # at the end? -> place plain
            if next == None:
                dst += src
            # invalid
            elif next == ")":
                return None
            # begin NOT block
            else:
                has_wild = True
                dst += chr(P_NOT)
                blocks.append(P_NOTEND)
                flush_blocks = False

        # '?' - match a single character
        elif src == "?":
            has_wild = True
            dst += chr(P_SINGLE)

        # '(' - begin block of ORs
        elif src == "(":
            has_wild = True
            dst += chr(P_ORSTART)
            blocks.append(P_OREND)
            flush_blocks = False
        # '|' - next OR segment
        elif src == "|":
            dst = _pop_non_or(blocks, dst)
            if len(blocks) == 0:
                return None
            dst += chr(P_ORNEXT)
            flush_blocks = False
        # ')' - end OR block
        elif src == ")":
            dst = _pop_non_or(blocks, dst)
            if len(blocks) == 0:
                return None
            dst += chr(P_OREND)
            blocks.pop()

        # '[' ... ']' char class
        elif src == "[":
            has_wild = True
            # [~ ... ] inverse class
            if next == "~":
                pos += 2
                dst += chr(P_NOTCLASS)
            # [ ... ] non inverse class
            else:
                pos += 1
                dst += chr(P_CLASS)
            while pos < n_src:
                ch = src_str[pos]
                if ch == "]":
                    break
                elif ch == "'":
                    pass
                else:
                    dst += tr(ch)
                pos += 1
            if pos == n_src:
                return None
            # terminate class with a CLASS, too
            dst += chr(P_CLASS)

        # '*' - any wildcard (if enabled)
        elif src == "*":
            if star_is_wild:
                has_wild = True
                dst += chr(P_ANY)
            else:
                dst += src

        # '%' - match nothing (for OR blocks)
        elif src == "%":
            flush_blocks = False

        # '\'' - quote next char
        elif src == "'":
            if next in "#*?(|)~[]%'":
                dst += next
                pos += 1
            elif star_is_wild and next == "*":
                dst += next
                pos += 1
            else:
                pass

        # any other non-wildcard char
        else:
            dst += tr(src)

        pos += 1
        if flush_blocks:
            dst = _pop_non_or(blocks, dst)

    # finally check blocks
    if len(blocks) > 0:
        return None

    return Pattern(src_str, dst, ignore_case, has_wild)


def _dump(num, level, txt):
    print("%02d" % num, " " * level, txt)


def pattern_dump(pattern):
    level = 0
    num = 0
    for d in pattern.pat_str:
        o = ord(d)
        if o in p_txt:
            if o in (P_ORSTART, P_REPBEG, P_NOT):
                _dump(num, level, p_txt[o])
                level += 1
            elif o in (P_OREND, P_REPEND, P_NOTEND):
                level -= 1
                _dump(num, level, p_txt[o])
            elif o == P_ORNEXT:
                _dump(num, level - 1, p_txt[o])
            else:
                _dump(num, level, p_txt[o])
        else:
            _dump(num, level, d)
        num += 1


# ----- pattern matcher -----


class Marker:
    def __init__(self, flag, pat_pos, str_pos):
        self.flag = flag
        self.pat_pos = pat_pos
        self.str_pos = str_pos

    def __str__(self):
        return "[%s:pat=%d,str=%d]" % (self.flag, self.pat_pos, self.str_pos)

    def get(self):
        return (self.flag, self.pat_pos, self.str_pos)

    def same(self, o):
        return (
            self.flag == o.flag
            and self.pat_pos == o.pat_pos
            and self.str_pos == o.str_pos
        )


class MarkerStack:
    def __init__(self):
        self.stack = []
        self.history = []

    def push(self, marker):
        # add only if not already in history
        found = False
        for h in self.history:
            if h.same(marker):
                found = True
                break
        if not found:
            self.stack.append(marker)

    def pop(self):
        if len(self.stack) > 0:
            m = self.stack.pop()
            # store in history
            self.history.append(m)
            return m
        else:
            return None

    def get_last(self, flag):
        pos = len(self.stack) - 1
        while pos >= 0:
            if self.stack[pos].flag == flag:
                return pos
            pos -= 1
        return None

    def get(self, pos):
        return self.stack[pos]

    def drop(self, pos):
        # drop markers including the one at pos
        self.stack = self.stack[:pos]

    def __str__(self):
        return ",".join(map(str, self.stack))


def _seek_end(pat, pat_pos, p_beg, p_end):
    nesting = 1
    while True:
        cmd = ord(pat[pat_pos])
        if cmd == p_beg:
            nesting += 1
        elif cmd == p_end:
            nesting -= 1
            if nesting == 0:
                return pat_pos
        pat_pos += 1


def _seek_begin(pat, pat_pos, p_beg, p_end):
    nesting = 1
    while True:
        cmd = ord(pat[pat_pos])
        if cmd == p_end:
            nesting += 1
        elif cmd == p_beg:
            nesting -= 1
            if nesting == 0:
                return pat_pos
        pat_pos -= 1


def _scan_or_block(pat, pat_pos, str_pos, markers):
    nesting = 1
    while True:
        cmd = ord(pat[pat_pos])
        if cmd == P_ORSTART:
            nesting += 1
        elif cmd == P_OREND:
            nesting -= 1
            if nesting == 0:
                return
        elif cmd == P_ORNEXT:
            if nesting == 1:
                markers.push(Marker(False, pat_pos + 1, str_pos))
        pat_pos += 1


def pattern_match(pattern, in_str, debug=False):
    """match pattern pat against str and return True/False"""
    if pattern.ignore_case:
        tr = lambda x: x.lower()
    else:
        tr = lambda x: x

    pat = pattern.pat_str
    markers = MarkerStack()
    pat_pos = 0
    str_pos = 0
    n_pat = len(pat)
    n_str = len(in_str)

    while True:
        get_next_marker = False

        # get next pattern character/command
        if pat_pos < n_pat:
            p_ch = pat[pat_pos]
            cmd = ord(p_ch)
        else:
            p_ch = "\0"
            cmd = 0

        # DEBUG
        if debug:
            if cmd in p_txt:
                cmdx = p_txt[cmd]
            else:
                cmdx = p_ch
            print(
                "match: pat_pos=%d str_pos=%d p_ch=%s markers=%s"
                % (pat_pos, str_pos, cmdx, markers)
            )

        # --- REPBEG - repeat begin ----------------------------------------------
        if cmd == P_REPBEG:
            pat_pos += 1
            # add a marker for repeat of this block
            markers.push(Marker(False, pat_pos, str_pos))
            # for now assume we skip this block
            pat_pos = _seek_end(pat, pat_pos, P_REPBEG, P_REPEND) + 1

        # --- REPEND - repeat end ------------------------------------------------
        elif cmd == P_REPEND:
            # rewind pat_pos to P_REPBEG of block
            pat_pos = _seek_begin(pat, pat_pos - 1, P_REPBEG, P_REPEND)

        # --- NOT - begin not block ----------------------------------------------
        elif cmd == P_NOT:
            pat_pos += 1
            pat_end = _seek_end(pat, pat_pos, P_NOT, P_NOTEND) + 1
            # add a marker skipping the NOT pattern at this string
            markers.push(Marker(True, pat_end, str_pos))
            # we continue to scan the NOT expression
            # if it succeeds then NOTEND is reached -> path will fail as we matched the NOT expr
            # otherwise this pushed marker will continue with pattern scanning

        # --- NOTEND - end not block reached -------------------------------------
        elif cmd == P_NOTEND:
            # get my pushed NOT marker
            pos = markers.get_last(True)
            # string end?
            if str_pos == n_str:
                # drop all markers including my NOT marker
                markers.drop(pos)
                if debug:
                    print("strip markers, pos=", pos)
            else:
                m = markers.get(pos)
                str_pos += 1
                # update match pos of my NOT marker to use current string pos
                if str_pos > m.str_pos:
                    m.str_pos = str_pos
                    if debug:
                        print("update marker:", m)

            # try next marker
            get_next_marker = True

        # --- ORSTART ------------------------------------------------------------
        elif cmd == P_ORSTART:
            pat_pos += 1
            # find all alternatives and push them as markers
            _scan_or_block(pat, pat_pos, str_pos, markers)

        # --- ORNEXT -------------------------------------------------------------
        elif cmd == P_ORNEXT:
            pat_pos += 1
            # skip over rest of OR block
            pat_pos = _seek_end(pat, pat_pos, P_ORSTART, P_OREND) + 1

        # --- OREND --------------------------------------------------------------
        elif cmd == P_OREND:
            pat_pos += 1

        # --- SINGLE -------------------------------------------------------------
        elif cmd == P_SINGLE:
            pat_pos += 1
            # match existing char
            if str_pos < n_str:
                str_pos += 1
            # no more string left -> try next
            else:
                get_next_marker = True

        # --- CLASS (character class) [...] --------------------------------------
        elif cmd == P_CLASS:
            # string already consumed?
            if str_pos == n_str:
                get_next_marker = True
            else:
                pat_pos += 1
                while True:
                    # get next char in class
                    p_ch = pat[pat_pos]
                    cmd = ord(p_ch)
                    pat_pos += 1

                    # range
                    begin = cmd
                    end = cmd

                    # end of class
                    if cmd == P_CLASS:
                        get_next_marker = True
                        break

                    # range '-'
                    if pat[pat_pos] == "-":
                        pat_pos += 1
                        end = ord(pat[pat_pos])
                        # end '-]' -> match until 255
                        if end == P_CLASS:
                            end = 255

                    # check string against class -> match!
                    s_ch = ord(tr(in_str[str_pos]))
                    if s_ch >= begin and s_ch <= end:
                        str_pos += 1
                        # move to end of pattern
                        while ord(pat[pat_pos]) != P_CLASS:
                            pat_pos += 1
                        # move after closing P_CLASS
                        pat_pos += 1
                        break

        # --- NOTCLASS negated character class [~...] ----------------------------
        elif cmd == P_NOTCLASS:
            # string already consumed?
            if str_pos == n_str:
                get_next_marker = True
            else:
                pat_pos += 1
                while True:
                    # get next char in class
                    p_ch = pat[pat_pos]
                    cmd = ord(p_ch)
                    pat_pos += 1

                    # character range
                    begin = cmd
                    end = cmd

                    # end of class -> ok
                    if cmd == P_CLASS:
                        str_pos += 1
                        break

                    # range in class
                    if pat[pat_pos] == "-":
                        pat_pos += 1
                        end = ord(pat[pat_pos])
                        # end '-]' -> match until 255
                        if end == P_CLASS:
                            end = 255

                    # check if character is in range -> NOTCLASS missed!
                    s_ch = ord(tr(in_str[str_pos]))
                    if s_ch >= begin and s_ch <= end:
                        # try next marker
                        get_next_marker = True
                        break

        # --- ANY #? -------------------------------------------------------------
        elif cmd == P_ANY:
            # add a try with ANY and next string pos
            if str_pos < n_str:
                markers.push(Marker(False, pat_pos, str_pos + 1))
            pat_pos += 1

        # --- EOF end of pattern -------------------------------------------------
        elif cmd == 0:
            # string also at end -> MATCH!
            if str_pos == n_str:
                return True
            else:
                # try next marker
                get_next_marker = True

        # --- non-wildcard CHAR --------------------------------------------------
        else:
            # get next string char
            if str_pos < n_str:
                s_ch = tr(in_str[str_pos])
            else:
                s_ch = "\0"

            # char matched
            if p_ch == s_ch:
                str_pos += 1
                pat_pos += 1
                if debug:
                    print("\tchar match: %c == %c" % (p_ch, s_ch))

            # no char match
            else:
                if debug:
                    print("\tchar mismatch: %c != %c" % (p_ch, s_ch))
                get_next_marker = True

        # get next marker to try
        if get_next_marker:
            m = markers.pop()
            if m == None:
                if debug:
                    print("no next marker. end")
                return False
            if debug:
                print("next marker:", m, " on stack:", markers)
            (flag, pat_pos, str_pos) = m.get()
            if flag and str_pos < n_str:
                markers.push(Marker(True, pat_pos, str_pos + 1))


# ----- test -----
if __name__ == "__main__":
    import sys

    a = sys.argv[1:]
    a_n = len(a)
    if a_n < 1:
        print("Usage:", sys.argv[0], "<pattern> [match]")
    else:
        pat = pattern_parse(a[0])
        if pat == None:
            print("Error parsing pattern!")
            sys.exit(1)
        else:
            pattern_dump(pat)
            if a_n > 1:
                for a in sys.argv[2:]:
                    match = pattern_match(pat, a, debug=True)
                    print("'%s' -> %s" % (a, match))
