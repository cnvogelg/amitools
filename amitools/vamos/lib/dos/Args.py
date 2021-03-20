import types
from .Error import *
from .Item import ItemParser


class TemplateArg:
    """a parsed description of a template argument"""

    TYPE_STRING = 0
    TYPE_NUMBER = 1
    TYPE_SWITCH = 2
    TYPE_TOGGLE = 3
    TYPE_FULL = 4

    def __init__(
        self, keys, ktype, is_keyword=False, is_required=False, is_multi=False
    ):
        self.keys = keys
        self.ktype = ktype
        self.is_keyword = is_keyword
        self.is_required = is_required
        self.is_multi = is_multi
        self.pos = 0

    def __str__(self):
        return "(#%d:%s,%d,k=%s,r=%s,m=%s)" % (
            self.pos,
            ",".join(self.keys),
            self.ktype,
            self.is_keyword,
            self.is_required,
            self.is_multi,
        )

    def has_key(self, name):
        key = name.upper()
        return key in self.keys

    @classmethod
    def parse_string(cls, template):
        """parse a template string keya=keyb/n/k"""
        # allow empty key!
        p = [x for x in template.split("/")]
        if len(p) == 0:
            return None
        keys_all = p[0]
        flags_all = p[1:]
        # keys
        keys = [x.upper() for x in keys_all.split("=")]
        if len(keys) == 0:
            return None
        # flags
        flags = [x[0].upper() for x in flags_all]
        ktype = cls.TYPE_STRING
        is_keyword = False
        is_required = False
        is_multi = False
        for ch in flags:
            if ch == "N":
                ktype = cls.TYPE_NUMBER
            elif ch == "S":
                ktype = cls.TYPE_SWITCH
                is_keyword = True
            elif ch == "T":
                ktype = cls.TYPE_TOGGLE
                is_keyword = True
            elif ch == "A":
                is_required = True
            elif ch == "K":
                is_keyword = True
            elif ch == "M":
                is_multi = True
            elif ch == "F":
                ktype = cls.TYPE_FULL
        return TemplateArg(keys, ktype, is_keyword, is_required, is_multi)


class TemplateArgList:
    """a parsed list of TemplateArg"""

    def __init__(self):
        self.targs = []

    def __str__(self):
        return "[#%d:%s]" % (self.len(), ",".join(map(str, self.targs)))

    def append(self, targ):
        targ.pos = len(self.targs)
        self.targs.append(targ)

    def len(self):
        return len(self.targs)

    def get_arg(self, pos):
        if pos < 0 or pos >= len(self.targs):
            return None
        else:
            return self.targs[pos]

    def find_arg(self, name):
        for t in self.targs:
            if t.has_key(name):
                return t

    @staticmethod
    def parse_string(template):
        tal = TemplateArgList()
        ps = template.split(",")
        for p in ps:
            if p != "":
                targ = TemplateArg.parse_string(p)
                if targ is None:
                    return None
                tal.append(targ)
        return tal


class ParseResultList:
    """the class holds the parsing results. each template arg gets assigned
    a single item (or not)"""

    def __init__(self, targ_list):
        """create with a template arg list"""
        self.targ_list = targ_list
        self.len = targ_list.len()
        self.result = [None] * self.len

    def __str__(self):
        return ",".join(map(str, self.result))

    def get_result(self, pos):
        if pos < self.len:
            return self.result[pos]

    def set_result(self, pos, val):
        if pos < self.len:
            self.result[pos] = val

    def get_results(self):
        return self.result

    def calc_extra_result_size(self):
        """return size of extra result in bytes.
        we count the longs and chars that do not fit into the
        result long array passed into ReadArgs()

        return size in bytes, number of longs
        """
        num = self.len
        num_longs = 0
        num_chars = 0
        for pos in range(num):
            r = self.result[pos]
            if r is not None:
                targ = self.targ_list.get_arg(pos)
                ktype = targ.ktype
                if targ.is_multi:
                    # account list itself + null long
                    n = len(r)
                    if n > 0:
                        num_longs += n + 1
                        if ktype == TemplateArg.TYPE_STRING:
                            # reserve string + null byte
                            for s in r:
                                num_chars += len(s) + 1
                        elif ktype == TemplateArg.TYPE_NUMBER:
                            # reserve longs
                            num_longs += n
                elif ktype in (TemplateArg.TYPE_STRING, TemplateArg.TYPE_FULL):
                    # store string + null byte
                    num_chars += len(r) + 1
                elif ktype == TemplateArg.TYPE_NUMBER:
                    num_longs += 1

        # calc total size
        size = num_longs * 4 + num_chars
        return size, num_longs

    def generate_result(self, mem_access, array_ptr, extra_ptr, num_longs):
        """now convert the values into memory array and extra array"""
        num = self.len
        char_ptr = extra_ptr + num_longs * 4
        long_ptr = extra_ptr
        for pos in range(num):
            targ = self.targ_list.get_arg(pos)
            ktype = targ.ktype
            r = self.result[pos]
            base_val = None
            if r is None:
                if targ.is_multi:
                    # always set array pointer to 0
                    base_val = 0
            else:
                if targ.is_multi:
                    n = len(r)
                    if n == 0:
                        base_val = 0
                    else:
                        if ktype == TemplateArg.TYPE_STRING:
                            # pointer to array
                            base_val = long_ptr
                            for s in r:
                                mem_access.w32(long_ptr, char_ptr)
                                mem_access.w_cstr(char_ptr, s)
                                long_ptr += 4
                                char_ptr += len(s) + 1
                        elif ktype == TemplateArg.TYPE_NUMBER:
                            # first the values
                            val_ptr = long_ptr
                            # then the pointers to the values
                            long_ptr += n * 4
                            base_val = long_ptr
                            for i in r:
                                mem_access.w32(long_ptr, val_ptr)
                                mem_access.w32(val_ptr, i)
                                long_ptr += 4
                                val_ptr += 4
                        # terminate pointer list
                        mem_access.w32(long_ptr, 0)
                        long_ptr += 4
                elif ktype in (TemplateArg.TYPE_STRING, TemplateArg.TYPE_FULL):
                    # store string + null byte
                    base_val = char_ptr
                    # append string
                    mem_access.w_cstr(char_ptr, r)
                    char_ptr += len(r) + 1
                elif ktype == TemplateArg.TYPE_NUMBER:
                    # pointer to long
                    base_val = long_ptr
                    # write long
                    mem_access.w32(long_ptr, r)
                    long_ptr += 4
                elif ktype == TemplateArg.TYPE_SWITCH:
                    base_val = 0xFFFFFFFF
                elif ktype == TemplateArg.TYPE_TOGGLE:
                    old_val = mem_access.r32(array_ptr)
                    base_val = 0 if old_val else 0xFFFFFFFF

            # update array pointer
            if base_val is not None:
                mem_access.w32(array_ptr, base_val)
            array_ptr += 4


class ArgsParser:
    """perform ReadArgs()-style parsing"""

    def __init__(self, targ_list):
        """setup parser with parsed template argument list"""
        self.targ_list = targ_list
        self.result_list = None
        self.len = targ_list.len()

    def parse(self, csrc, maxbuf=256):
        """input is read from csrc
        return NO_ERROR or ERROR_*
        """
        result_list = ParseResultList(self.targ_list)
        self.result_list = result_list
        item_parser = ItemParser(csrc, eol_unget_bug=False)

        # ----- first pass -----
        # run through targs and check if a value is found on csrc
        pos = 0
        num_targ = result_list.len
        multi_buffer = []
        item = ItemParser.ITEM_NOTHING
        while pos <= num_targ:
            # skip values that were alreay set
            if result_list.get_result(pos) is not None:
                pos += 1
                continue
            # skip keyword entries. they will be found if a corresponding item occurs
            targ = self.targ_list.get_arg(pos)
            if targ is not None and targ.is_keyword:
                pos += 1
                continue

            # normally we walk to the next targ, but keywords may hop at other pos
            next_pos = pos + 1

            # read next item from stream
            item, data = item_parser.read_item(maxbuf)
            if item == ItemParser.ITEM_ERROR:
                return ERROR_LINE_TOO_LONG
            elif item == ItemParser.ITEM_NOTHING:
                # leave first stage
                break
            elif item == ItemParser.ITEM_EQUAL:
                return ERROR_BAD_TEMPLATE
            elif item == ItemParser.ITEM_UNQUOTED:
                # is the item a keyword?
                key_targ = self.targ_list.find_arg(data)
                if key_targ is not None:
                    # yes its a keyword
                    key_pos = key_targ.pos
                    # is still empty?
                    if result_list.get_result(key_pos) is None:
                        # next time retry current targ again
                        next_pos = pos
                        # ok let's process it
                        pos = key_pos
                        targ = key_targ
                        # do we need a value after the key?
                        if targ.ktype not in (
                            TemplateArg.TYPE_TOGGLE,
                            TemplateArg.TYPE_SWITCH,
                        ):
                            vitem, data = item_parser.read_item(maxbuf)
                            if vitem == ItemParser.ITEM_EQUAL:
                                # read next value
                                vitem, data = item_parser.read_item(maxbuf)
                            if vitem not in (
                                ItemParser.ITEM_QUOTED,
                                ItemParser.ITEM_UNQUOTED,
                            ):
                                return ERROR_KEY_NEEDS_ARG

            # /F get full string
            if targ is not None and targ.ktype == TemplateArg.TYPE_FULL:
                # get full text
                full = data + item_parser.read_eol()
                result_list.set_result(pos, full)
                break
            # /M first collect all multi entries
            # last pos == num_targ is also a "fake" multi target to collect all
            # remaining items
            elif pos == num_targ or targ.is_multi:
                multi_buffer.append(data)
                # read again
                next_pos = pos
            # /S or /T
            elif targ.ktype in (TemplateArg.TYPE_TOGGLE, TemplateArg.TYPE_SWITCH):
                result_list.set_result(pos, True)
            # /N number or string: store string value
            else:
                result_list.set_result(pos, data)

            # next iteration
            pos = next_pos

        # save last targ pos
        last_pos = pos

        # ----- 2nd pass -----
        # fill in required (/A) args from multi buffer (backwards!)
        pos = num_targ - 1
        while pos >= 0:
            targ = self.targ_list.get_arg(pos)
            res = result_list.get_result(pos)
            # no value for required arg yet?
            if targ.is_required and not targ.is_multi and res is None:
                # if its a keyword argument its too late
                # keyword should have been filled already in 1st pass
                if targ.is_keyword:
                    return ERROR_TOO_MANY_ARGS
                # nothing in multi buffer?
                if len(multi_buffer) == 0:
                    return ERROR_REQUIRED_ARG_MISSING
                # grab from multi buffer
                result_list.set_result(pos, multi_buffer.pop())
            pos -= 1

        # now assign remaining multi buffer
        num_multi = len(multi_buffer)
        for pos in range(num_targ):
            targ = self.targ_list.get_arg(pos)
            if targ.is_multi:
                # required but empty?
                if targ.is_required and num_multi == 0:
                    return ERROR_REQUIRED_ARG_MISSING
                # consume buffer
                if num_multi > 0:
                    result_list.set_result(pos, multi_buffer)
                    num_multi = 0
                break

        # are there still arguments left?
        if num_multi > 0 and last_pos == num_targ:
            return ERROR_TOO_MANY_ARGS

        # ----- 3rd pass -----
        # convert numbers
        return self._convert_numbers(result_list)

    def get_result_list(self):
        return self.result_list

    def _convert_numbers(self, result_list):
        for pos in range(self.len):
            targ = self.targ_list.get_arg(pos)
            # is arg a number?
            if targ.ktype == TemplateArg.TYPE_NUMBER:
                res = result_list.get_result(pos)
                if res is not None:
                    # convert number list
                    if targ.is_multi:
                        nlist = result_list.get_result(pos)
                        nres = []
                        for nstr in nlist:
                            num = self._convert_number(nstr)
                            if num is None:
                                return ERROR_BAD_NUMBER
                            nres.append(num)
                        result_list.set_result(pos, nres)
                    # convert single number
                    else:
                        nstr = result_list.get_result(pos)
                        num = self._convert_number(nstr)
                        if num is None:
                            return ERROR_BAD_NUMBER
                        result_list.set_result(pos, num)
        return NO_ERROR

    def _convert_number(self, data):
        try:
            n = int(data)
            if n >= 0 and n <= 0xFFFFFFFF:
                return n
        except ValueError:
            pass


class ArgsHelp:
    """check if argument help was requested"""

    def __init__(self, csrc):
        self.csrc = csrc
        self.num = 0

    def want_help(self):
        """check if a line has a '?' as a help request.
        if yes return True and consume the whole line from csrc.
        otherwise return False and rewind the whole line from csrc.
        """
        escaped = False
        quoted = False
        seen_space = True
        seen_question = False
        num = 0
        while True:
            c = self.csrc.getc()
            if c is None:
                break
            num += 1
            # quote/escape state tracking
            if c == "*":
                if quoted:
                    escaped = not escaped
            elif c == '"':
                if not escaped:
                    quoted = not quoted
            # check contents
            if c in (" ", "\t"):
                seen_space = True
            if c == "?":
                if not quoted and seen_space:
                    seen_question = True
                    seen_space = False
                else:
                    seen_question = False
            elif c == "\n":
                break
            else:
                seen_question = False
                seen_space = False
        # result
        self.num = num
        return seen_question

    def get_num_bytes(self):
        return self.num
