from .cfgdict import ConfigDict


def _check_enum(val, enum):
    if enum and val not in enum:
        raise ValueError("invalid enum: %s of %s" % (val, enum))


def parse_scalar(val_type, val, allow_none=False, enum=None):
    if type(val) is val_type:
        _check_enum(val, enum)
        return val
    # none handling
    if val is None:
        if allow_none:
            return None
        else:
            raise ValueError("None not allowed for type: %s" % val_type)
    # bool special strings
    if val_type is bool:
        if type(val) is str:
            lv = val.lower()
            if lv in ("on", "true"):
                return True
            elif lv in ("off", "false"):
                return False
    # int special strings
    if val_type is int:
        if type(val) is str:
            if val.startswith("0x"):
                val = int(val[2:], 16)
            elif val.startswith("$"):
                val = int(val[1:], 16)
    # convert type
    val = val_type(val)
    _check_enum(val, enum)
    return val


def split_nest(in_str, sep=",", nest_pair="()", keep_nest=False):
    """split a string by sep, but don't touch seps in nested pairs"""
    res = []
    cur = []
    nesting = 0
    if nest_pair is None:
        nest_begin = None
        nest_end = None
    else:
        nest_begin = nest_pair[0]
        nest_end = nest_pair[1]
    # split string loop
    for c in in_str:
        if c == nest_end:
            nesting -= 1
        if nesting == 0:
            if c in sep:
                if len(cur) > 0:
                    res.append("".join(cur))
                    cur = []
            elif c not in (nest_begin, nest_end) or keep_nest:
                cur.append(c)
        else:
            cur.append(c)
        # adjust nesting
        if c == nest_begin:
            nesting += 1
    # final element
    if len(cur) > 0:
        res.append("".join(cur))
    return res


class Value(object):
    def __init__(self, item_type, default=None, allow_none=None, enum=None):
        self.item_type = item_type
        self.nest_pair = None
        if allow_none is None:
            self.allow_none = item_type is str
        else:
            self.allow_none = allow_none
        self.enum = enum
        if default is not None:
            self.default = self.parse(default)
        else:
            self.default = None

    def parse(self, val, old_val=None):
        return parse_scalar(self.item_type, val, self.allow_none, self.enum)

    def __eq__(self, other):
        return self.item_type == other.item_type and self.default == other.default

    def __repr__(self):
        return "Value(%s, default=%s, allow_none=%s)" % (
            self.item_type,
            self.default,
            self.allow_none,
        )


class ValueList(object):
    def __init__(
        self,
        item_type,
        default=None,
        allow_none=None,
        enum=None,
        sep=",",
        nest_pair="()",
        clear_mark="*",
        allow_split=True,
    ):
        self.item_type = item_type
        self.sep = sep
        self.nest_pair = nest_pair
        self.clear_mark = clear_mark
        self.allow_split = allow_split
        self.is_sub_value = type(item_type) in (Value, ValueList, ValueDict)
        if self.is_sub_value:
            self.sub_nest_pair = item_type.nest_pair
        else:
            self.sub_nest_pair = None
        if allow_none is None:
            self.allow_none = item_type is str
        else:
            self.allow_none = allow_none
        self.enum = enum
        if default:
            self.default = self.parse(default)
        else:
            self.default = None

    def parse(self, val, old_val=None):
        if val is None:
            return []
        elif type(val) is str:
            # split string by sep
            if self.allow_split:
                val = split_nest(val, self.sep, self.sub_nest_pair)
            else:
                val = [val]
            recurse = False
        elif type(val) in (list, tuple):
            recurse = True
        else:
            raise ValueError("expected list or tuple: %s" % val)
        # start with old_val if available
        if old_val:
            res = old_val[:]
        else:
            res = []
        # rebuild list
        for v in val:
            if v == self.clear_mark:
                # reset list
                res = []
            elif type(v) is str and recurse:
                # parse sub string
                res += self.parse(v)
            elif self.is_sub_value:
                r = self.item_type.parse(v)
                res.append(r)
            else:
                r = parse_scalar(self.item_type, v, self.allow_none, self.enum)
                res.append(r)
        return res

    def __eq__(self, other):
        return (
            self.item_type == other.item_type
            and self.default == other.default
            and self.sep == other.sep
            and self.nest_pair == other.nest_pair
            and self.clear_mark == other.clear_mark
            and self.allow_split == other.allow_split
        )

    def __repr__(self):
        return (
            "ValueList(%s, default=%s, sep=%s, nest_pair=%s, "
            "clear_mark=%s, allow_split=%s)"
            % (
                self.item_type,
                self.default,
                self.sep,
                self.nest_pair,
                self.clear_mark,
                self.allow_split,
            )
        )


class ValueDict(object):
    def __init__(
        self,
        item_type,
        default=None,
        allow_none=None,
        enum=None,
        sep=",",
        kv_sep=":",
        nest_pair="{}",
        clear_mark="*",
        valid_keys=None,
    ):
        self.item_type = item_type
        self.sep = sep
        self.kv_sep = kv_sep
        self.nest_pair = nest_pair
        self.clear_mark = clear_mark
        self.is_sub_value = type(item_type) in (Value, ValueList, ValueDict)
        if self.is_sub_value:
            self.sub_nest_pair = item_type.nest_pair
        else:
            self.sub_nest_pair = None
        if allow_none is None:
            self.allow_none = item_type is str
        else:
            self.allow_none = allow_none
        self.enum = enum
        self.valid_keys = valid_keys
        if default:
            self.default = self.parse(default)
        else:
            self.default = None

    def _str_to_dict(self, val):
        # convert str to dict
        d = {}
        # split string by ',' to separate key, val pairs
        kvs = split_nest(val, self.sep, self.sub_nest_pair, True)
        last_key = None
        has_clear = False
        for kv in kvs:
            # clear mark?
            if self.clear_mark == kv:
                d = {}
                has_clear = True
            # if colon is in substring assign value to key
            elif self.kv_sep in kv:
                elems = split_nest(kv, self.kv_sep, self.sub_nest_pair)
                n = len(elems)
                if n > 0:
                    key = elems[0]
                    # join extra colon elements
                    if n > 1:
                        val = self.kv_sep.join(elems[1:])
                    else:
                        val = ""
                    d[key] = val
                    last_key = key
                else:
                    raise ValueError("no colon found!")
            elif not last_key:
                raise ValueError("no key:value found!")
            else:
                # append this sub string to last key
                d[key] = d[key] + self.sep + kv
        return d, has_clear

    def parse(self, val, old_val=None):
        if val is None:
            return {}
        elif type(val) is str:
            val, has_clear = self._str_to_dict(val)
            if has_clear:
                old_val = None
        elif type(val) in (list, tuple):
            # allow list of entries and merge them
            res = ConfigDict()
            for elem in val:
                d = self.parse(elem, old_val)
                res.update(d)
                old_val = d
            return res
        elif type(val) not in (dict, ConfigDict):
            raise ValueError("expected dict: %s" % val)
        # rebuild dict
        if old_val:
            res = old_val.copy()
        else:
            res = ConfigDict()
        for key in val:
            # check key
            if self.valid_keys and key not in self.valid_keys:
                raise ValueError("invalid key %s in %s" % (key, self.valid_keys))
            # convert value
            v = val[key]
            if self.is_sub_value:
                if old_val and key in old_val:
                    old_sub = old_val[key]
                else:
                    old_sub = None
                r = self.item_type.parse(v, old_sub)
            else:
                r = parse_scalar(self.item_type, v, self.allow_none, self.enum)
            res[key] = r
        return res

    def __eq__(self, other):
        return (
            self.item_type == other.item_type
            and self.default == other.default
            and self.sep == other.sep
            and self.kv_sep == other.kv_sep
            and self.nest_pair == other.nest_pair
            and self.clear_mark == other.clear_mark
        )

    def __repr__(self):
        return (
            "ValueDict(%s, default=%s, sep=%s, kv_sep=%s, "
            "nest_pair=%s, clear_mark=%s)"
            % (
                self.item_type,
                self.default,
                self.sep,
                self.kv_sep,
                self.nest_pair,
                self.clear_mark,
            )
        )
