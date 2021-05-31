from amitools.vamos.log import log_path
from amitools.vamos.cfgcore import split_nest
from .spec import Spec


class Assign(object):
    def __init__(self, name, assigns, cfg=None):
        if cfg is None:
            cfg = {}
        self.name = name
        self.assigns = assigns
        self.lo_name = name.lower()
        self.cfg = cfg
        self.is_setup = False

    def __str__(self):
        return "Assign(%s(%s):%r,cfg=%r)" % (
            self.name,
            self.lo_name,
            self.assigns,
            self.cfg,
        )

    def get_name(self):
        """return original name of assign"""
        return self.name

    def get_lo_name(self):
        """return normalized name of assign, i.e. lower case"""
        return self.lo_name

    def get_assigns(self):
        """return list of assigned paths"""
        return self.assigns

    def get_cfg(self):
        """return assign config"""
        return self.cfg

    def append(self, paths):
        self.assigns += paths

    def setup(self, mgr):
        vmgr = mgr.get_volume_mgr()
        for a in self.assigns:
            log_path.info("assign '%s': checking: %s", self.name, a)
            # check assign
            volpaths = mgr.resolve_assigns(a, as_list=True)
            for volpath in volpaths:
                res = mgr._split_volume_remainder(volpath)
                if res is None:
                    log_path.error(
                        "assign '%s': no absolute path: %s", self.name, volpath
                    )
                    return False
                # resolve volume
                volname, rel_dir = res
                volume = vmgr.get_volume(volname)
                if not volume:
                    log_path.error("assign '%s': volume not found: %s", self.name, a)
                    return False
                # create assign dir?
                if "create" in self.cfg:
                    if not self._create_dir(volume, rel_dir):
                        return False
        return True

    def _create_dir(self, volume, rel_dir):
        log_path.debug("%s: create assign dir: rel_dir='%s'", self.name, rel_dir)
        path = volume.create_rel_sys_path(rel_dir)
        if not path:
            log_path.error(
                "assign '%s': can't create relative dir: %s", self.name, rel_dir
            )
            return False
        else:
            log_path.debug("created sys path: %s", path)
            return True

    def shutdown(self):
        pass


class AssignManager(object):
    def __init__(self, vol_mgr):
        self.vol_mgr = vol_mgr
        self.assigns = []
        self.is_setup = False
        self.assigns_by_name = {}

    def get_volume_mgr(self):
        return self.vol_mgr

    def parse_config(self, cfg):
        if cfg is None:
            return True
        assigns = cfg.assigns
        if assigns is None:
            return True
        for spec in assigns:
            if not self.add_assign(spec):
                return False
        return True

    def dump(self):
        log_path.info("--- assigns ---")
        for a in self.assigns:
            log_path.info("%s", a)

    def setup(self):
        log_path.debug("setting up assigns")
        for a in self.assigns:
            if not a.setup(self):
                log_path.error("error setting up assign: %s", a)
                return False
            a.is_setup = True
        self.is_setup = True
        return True

    def shutdown(self):
        log_path.debug("shutting down assigns")
        for a in self.assigns:
            log_path.info("cleaning up assign: %s", a)
            a.shutdown()
            a.is_setup = False

    def get_all_names(self):
        return [x.get_name() for x in self.assigns]

    def get_assign(self, name):
        lo_name = name.lower()
        if lo_name in self.assigns_by_name:
            return self.assigns_by_name[lo_name]

    def is_assign(self, name):
        return name.lower() in self.assigns_by_name

    def add_assigns(self, specs, force=False):
        if not assigns:
            return []
        res = []
        for spec in specs:
            a = self.add_assign(assign, alist)
            if not a:
                return False
            res.append(a)
        return res

    def add_assign(self, spec):
        assign = self._parse_spec(spec)
        if assign is None:
            return None

        # check name: is volume?
        lo_name = assign.get_lo_name()
        if self.vol_mgr.is_volume(lo_name):
            log_path.error("assign with a volume name is not allowed: %s", lo_name)
            return None
        # check name: duplicate assign
        elif lo_name in self.assigns_by_name:
            # after setup do not allow duplicate volumes
            if self.is_setup:
                log_path.error("duplicate assign: %s", lo_name)
                return None
            # before setup simply overwrite existing assign
            else:
                old_assign = self.assigns_by_name[lo_name]
                log_path.info("overwriting assign: %s", old_assign)
                self.assigns.remove(old_assign)
                del self.assigns_by_name[lo_name]

        # after global setup try to setup assign immediately
        if self.is_setup:
            if not assign.setup(self):
                log_path.error("error setting up assign: %s", assign)
                return None
            assign.is_setup = True

        # finally add assign
        log_path.info("adding assign: %s", assign)
        self.assigns_by_name[lo_name] = assign
        self.assigns.append(assign)
        return assign

    def del_assign(self, name):
        lo_name = name.lower()
        if lo_name not in self.assigns_by_name:
            return False
        a = self.assigns_by_name[lo_name]
        a.shutdown()
        a.is_setup = False
        self.assigns.remove(a)
        del self.assigns_by_name[lo_name]
        log_path.info("delete assign: %s", a)
        return True

    def _parse_spec(self, spec):
        # auto convert spec string
        if type(spec) is str:
            try:
                spec = Spec.parse(spec)
            except ValueError as e:
                log_path.error("error parsing spec: %r -> %s", spec, e)
                return None
        # check spec
        append = spec.get_append()
        name = spec.get_name()
        cfg = spec.get_cfg()
        elements = spec.get_src_list()
        if len(elements) == 0:
            log_path.error("no elements in assign: %r", spec)
            return None
        # append?
        if append:
            assign = self.get_assign(name)
            if assign:
                log_path.info(
                    "appending to existing assign: name='%s': %r", name, elements
                )
                assign.append(elements)
                return assign
            log_path.warning("can't append to non-existing assign: '%s'", name)
            # fall through
        log_path.info("create new assign: name='%s': %r", name, elements)
        return Assign(name, elements, cfg)

    def _split_volume_remainder(self, ami_path):
        """return (volume, remainder) or none if no volume found"""
        pos = ami_path.find(":")
        # no assign expansion
        if pos <= 0:
            return None
        else:
            name = ami_path[:pos].lower()
            if ami_path[-1] == ":":
                remainder = None
            else:
                remainder = ami_path[pos + 1 :]
            return (name, remainder)

    def _concat_assign(self, aname, remainder):
        if remainder:
            if aname[-1] not in (":", "/"):
                return aname + "/" + remainder
            else:
                return aname + remainder
        else:
            return aname

    def resolve_assigns(self, ami_path, recursive=True, as_list=False):
        """replace all assigns found in path until only a volume path exists.
        do not touch relative paths or abs paths without assign prefix.

         return: original path if path is not absolute
                 or does not contain assign prefix
         or: string if no multi assigns are involved
         or: list of string if multi assigns were encountered
        """
        log_path.info("resolve_assign: ami_path='%s'", ami_path)
        split = self._split_volume_remainder(ami_path)
        if split is None:
            # relative path
            log_path.debug("resolve_assign: ami_path='%s' is rel_path!", ami_path)
            if as_list:
                return [ami_path]
            else:
                return ami_path
        else:
            # is assign
            name = split[0].lower()
            if name in self.assigns_by_name:
                remainder = split[1]
                assign = self.assigns_by_name[name]
                aname_list = assign.get_assigns()
                # single assign
                if len(aname_list) == 1:
                    aname = aname_list[0]
                    new_path = self._concat_assign(aname, remainder)
                    log_path.info(
                        "resolve_assign: ami_path='%s' -> single assign: '%s'",
                        ami_path,
                        new_path,
                    )
                    if recursive:
                        return self.resolve_assigns(new_path, recursive, as_list)
                    elif as_list:
                        return [new_path]
                    else:
                        return new_path
                # multi assign
                else:
                    result = []
                    for aname in aname_list:
                        new_path = self._concat_assign(aname, remainder)
                        log_path.info(
                            "resolve_assign: ami_path='%s' -> multi assign: '%s'",
                            ami_path,
                            new_path,
                        )
                        if recursive:
                            new_path = self.resolve_assigns(
                                new_path, recursive, as_list
                            )
                            if new_path is None:
                                return None
                        if type(new_path) is str:
                            result.append(new_path)
                        else:
                            result += new_path
                    return result
            # prefix is not an assign
            else:
                log_path.debug("resolve_assign: ami_path='%s' has no assign!", ami_path)
                if as_list:
                    return [ami_path]
                else:
                    return ami_path
