from .ProtectFlags import *
from .TimeStamp import *
from .FSString import FSString


class MetaInfo:
    def __init__(
        self,
        protect=None,
        mod_ts=None,
        comment=None,
        protect_flags=None,
        owner_uid=None,
        owner_gid=None,
    ):
        if protect_flags != None:
            self.set_protect_flags(protect_flags)
        else:
            self.set_protect(protect)
        self.set_mod_ts(mod_ts)
        self.set_comment(comment)
        self.set_owner(owner_uid, owner_gid)

    def get_str_line(self):
        """Return a unicode string with protect flags, mod time and (optional) comment"""
        res = []
        res.append(self.get_protect_str())
        prot = self.get_protect_extra_str()
        if prot:
            res.append(prot)
        owner = self.get_owner_str()
        if owner:
            res.append(owner)
        res.append(self.get_mod_time_str())
        comment = self.get_comment()
        if comment == None:
            res.append("")
        else:
            res.append(self.get_comment().get_unicode())
        return "  ".join(res)

    def get_owner_str(self):
        """the owner as ``uid gid``, or an empty string when it is 0/0"""
        uid = self.get_owner_uid()
        gid = self.get_owner_gid()
        if uid == 0 and gid == 0:
            return ""
        return "%d %d" % (uid, gid)

    def set_owner(self, uid, gid):
        """set the owner ids. ``None`` for both leaves the owner unchanged
        when this meta info is applied to a node"""
        self.owner_uid = uid
        self.owner_gid = gid

    def has_owner(self):
        """whether this meta info carries owner ids to apply"""
        return self.owner_uid is not None or self.owner_gid is not None

    def get_owner_uid(self):
        return self.owner_uid if self.owner_uid is not None else 0

    def get_owner_gid(self):
        return self.owner_gid if self.owner_gid is not None else 0

    def get_mod_time_str(self):
        if self.mod_ts != None:
            return str(self.mod_ts)
        else:
            return ts_empty_string

    def get_protect_str(self):
        if self.protect_flags != None:
            return str(self.protect_flags)
        else:
            return ProtectFlags.empty_string

    def get_protect_short_str(self):
        if self.protect_flags != None:
            return self.protect_flags.short_str()
        else:
            return ""

    def get_protect_extra_str(self):
        """hex form of the protection long, only when it has group/other/SUID
        bits the 8-char owner string cannot show"""
        if self.protect_flags is not None and self.protect_flags.has_extra():
            return self.protect_flags.extra_str()
        else:
            return ""

    def set_protect(self, protect):
        self.protect = protect
        if self.protect != None:
            self.protect_flags = ProtectFlags(protect)
        else:
            self.protect_flags = None

    def set_protect_flags(self, pf):
        self.protect_flags = pf
        self.protect = pf.mask

    def set_default_protect(self):
        self.protect = 0
        self.protect_flags = ProtectFlags(self.protect)

    def set_current_as_mod_time(self):
        mod_time = time.mktime(time.localtime())
        self.set_mod_time(mod_time)

    def set_mod_time(self, mod_time):
        self.mod_time = mod_time
        if self.mod_time != None:
            self.mod_ts = TimeStamp()
            self.mod_ts.from_secs(mod_time)
        else:
            self.mod_ts = None

    def set_mod_ts(self, mod_ts):
        self.mod_ts = mod_ts
        if self.mod_ts != None:
            self.mod_time = self.mod_ts.get_secsf()
        else:
            self.mod_time = None

    def set_comment(self, comment):
        """Set comment as a FSString"""
        if comment != None and not isinstance(comment, FSString):
            raise ValueError("Comment must be a FSString")
        self.comment = comment

    def get_protect(self):
        return self.protect

    def get_protect_flags(self):
        return self.protect_flags

    def get_mod_time(self):
        return self.mod_time

    def get_mod_ts(self):
        return self.mod_ts

    def get_comment(self):
        return self.comment

    def get_comment_ami_str(self):
        if self.comment != None:
            return self.comment.get_ami_str()
        else:
            return ""

    def get_comment_unicode_str(self):
        if self.comment != None:
            return self.comment.get_unicode()
        else:
            return ""
