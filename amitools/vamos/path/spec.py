from amitools.vamos.cfgcore import split_nest


class Spec(object):
    """a volume or assign specifier string parsed into components

    format:
      name:[+][src][+src][?key=val,key=val]
    """

    def __init__(self, name, src_list=None, cfg=None, append=False):
        if cfg is None:
            cfg = {}
        if src_list is None:
            src_list = []
        self.name = name
        self.src_list = src_list
        self.cfg = cfg
        self.append = append

    def __str__(self):
        return "Spec(name=%r,src_list=%r,append=%r,cfg=%r,valid=%r" % (
            self.name,
            self.src_list,
            self.append,
            self.cfg,
            self.valid,
        )

    @classmethod
    def parse(cls, spec):
        name = None
        src_list = []
        append = False
        cfg = {}
        # has optional config?
        cfg_pos = spec.find("?")
        if cfg_pos >= 0:
            cfg = cls._parse_cfg(spec[cfg_pos + 1 :])
            spec = spec[0:cfg_pos]
        # src start
        col_pos = spec.find(":")
        # no colon
        if col_pos == -1:
            name = spec
        elif col_pos == len(spec) - 1:
            name = spec[:-1]
        # a:foo
        elif col_pos > 0:
            name = spec[:col_pos]
            src = spec[col_pos + 1 :]
            if len(src) > 0:
                # append src list?
                if src[0] == "+":
                    append = True
                    src = src[1:]
            if len(src) > 0:
                src_list = split_nest(src, sep="+")
                if len(src_list) == 0:
                    raise ValueError("empty source list!")
                for src in src_list:
                    if len(src) == 0:
                        raise ValueError("contains empty source!")
            else:
                raise ValueError("empty source list!")
        # check name
        if name is None or name == "":
            raise ValueError("no name in spec!")
        return cls(name, src_list, cfg, append)

    @classmethod
    def _parse_cfg(cls, cfg_str):
        if len(cfg_str) == 0:
            raise ValueError("invalid config!")
        cfg_pairs = split_nest(cfg_str, sep=",")
        cfg = {}
        for p in cfg_pairs:
            kv = split_nest(p, sep="=")
            n = len(kv)
            if n == 1:
                key = kv[0]
                val = True
            elif n == 2:
                key, val = kv
                # value conversion
                vl = val.lower()
                if vl in ("true", "on", ""):
                    val = True
                elif vl in ("false", "off"):
                    val = False
            else:
                raise ValueError("not a key value pair in config!")
            if len(key) == 0:
                raise ValueError("invalid key!")
            cfg[key] = val
        return cfg

    def is_valid(self):
        return self.valid

    def get_src_list(self):
        return self.src_list

    def get_name(self):
        return self.name

    def get_append(self):
        return self.append

    def get_cfg(self):
        return self.cfg
