from .FSString import FSString


class FileName:
    root_path_aliases = ("", "/", ":")

    def __init__(self, name, is_intl=False, is_longname=False):
        # check that name is a FSString
        if not isinstance(name, FSString):
            raise ValueError("FileName's name must be a FSString")
        self.name = name
        self.is_intl = is_intl
        self.is_longname = is_longname

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def is_root_path_alias(self):
        return self.name.get_unicode() in self.root_path_aliases

    def has_dir_prefix(self):
        return self.name.get_unicode().find("/") != -1

    def split_path(self):
        pc = self.name.get_unicode().split("/")
        p = []
        for path in pc:
            p.append(
                FileName(
                    FSString(path), is_intl=self.is_intl, is_longname=self.is_longname
                )
            )
        return p

    def get_dir_and_base_name(self):
        """Return portion after last slash '/' or the full name in unicode"""
        s = self.name.get_unicode()
        pos = s.rfind("/")
        if pos != -1:
            dir_name = s[:pos]
            file_name = s[pos + 1 :]
            if len(file_name) == 0:
                return FSString(dir_name), None
            else:
                return FSString(dir_name), FSString(file_name)
        else:
            return None, self.name

    def get_upper_ami_str(self):
        result = self.name.get_ami_str().upper()
        if self.is_intl:
            r = bytearray()
            for i in range(len(result)):
                o = result[i]
                if o >= 224 and o <= 254 and o != 247:
                    r.append(o - (ord("a") - ord("A")))
                else:
                    r.append(o)
            return r
        else:
            return result

    def is_valid(self):
        # check if path contains dir prefix components
        if self.has_dir_prefix():
            e = self.split_path()
            # empty path?
            if len(e) == 0:
                return False
            for p in e:
                if not p.is_valid():
                    return False
            return True
        else:
            # single file name
            s = self.name.get_ami_str()
            # check for invalid chars
            for c in s:
                # o = ord(c)
                # if o == ':' or o == '/':
                # FIXME: FS
                if c == ":" or c == "/":
                    return False
            # check max size
            if self.is_longname:
                if len(s) > 110:
                    return False
            elif len(s) > 30:
                return False
        return True

    def hash(self, hash_size=72):
        up = self.get_upper_ami_str()
        h = len(up)
        for c in up:
            h = h * 13
            h += c
            h &= 0x7FF
        h = h % hash_size
        return h

    def get_name(self):
        """Return file name string as a FSString."""
        return self.name

    def get_ami_str_name(self):
        return self.name.get_ami_str()

    def get_unicode_name(self):
        return self.name.get_unicode()
