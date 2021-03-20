from amitools.vamos.log import log_path
from .amipath import AmiPath, AmiPathError
from .env import AmiPathEnv
from .volume import VolumeManager
from .assign import AssignManager


class SysPathError(Exception):
    def __init__(self, path, reason):
        self.path = path
        self.reason = reason

    def __str__(self):
        return "path='%s': %s" % (self.path, self.reason)


class PathManagerEnv(AmiPathEnv):
    def __init__(self, path_mgr, cwd=None, cmd_paths=None):
        self.path_mgr = path_mgr
        AmiPathEnv.__init__(self, cwd, cmd_paths)

    def _cwd_path_resolver(self, ami_path):
        """resolve and check cwd"""
        # allow escaped sys paths
        ami_path = self.path_mgr.resolve_esc_sys_path(ami_path, True)
        # common check
        ami_path = AmiPathEnv._cwd_path_resolver(self, ami_path)
        # make sure its a valid prefix path
        if not self.path_mgr.is_prefix_valid(ami_path):
            raise AmiPathError(ami_path, "cwd must have a valid prefix!")
        return ami_path

    def _cmd_path_resolver(self, ami_path):
        """resolve and check a command path"""
        # allow escaped sys paths
        ami_path = self.path_mgr.resolve_esc_sys_path(ami_path, True)
        # common check
        ami_path = AmiPathEnv._cmd_path_resolver(self, ami_path)
        # make sure its a valid prefix path
        if not self.path_mgr.is_prefix_valid(ami_path):
            raise AmiPathError(ami_path, "cmd path must have a valid prefix!")
        return ami_path


class PathManager:
    default_cwd = "::."
    default_cmd_paths = ["c:"]
    default_vols_base_dir = "~/.vamos/volumes"
    default_auto_volumes = ["root", "ram"]
    default_auto_assigns = ["c", "s", "libs", "devs", "t"]

    def __init__(
        self,
        cwd=None,
        cmd_paths=None,
        vols_base_dir=None,
        auto_volumes=None,
        auto_assigns=None,
        auto_assigns_mkdir=True,
        sys_vol=None,
    ):
        # set defaults
        if not cwd:
            cwd = self.default_cwd
        if not cmd_paths:
            cmd_paths = self.default_cmd_paths
        if not vols_base_dir:
            vols_base_dir = self.default_vols_base_dir
        if not auto_volumes:
            auto_volumes = self.default_auto_volumes
        if not auto_assigns:
            auto_assigns = self.default_auto_assigns
        # options
        self.auto_volumes = auto_volumes
        self.auto_assigns = auto_assigns
        self.auto_assigns_mkdir = auto_assigns_mkdir
        self.sys_vol = sys_vol
        # setup sub mgr
        self.vol_mgr = VolumeManager(vols_base_dir)
        self.assign_mgr = AssignManager(self.vol_mgr)
        self.default_env = PathManagerEnv(self, cwd, cmd_paths)

    def get_vol_mgr(self):
        return self.vol_mgr

    def get_assign_mgr(self):
        return self.assign_mgr

    def get_default_env(self):
        return self.default_env

    def create_env(self, cwd=None, cmd_paths=None):
        """return a new AmiPathEnv

        either share cwd or cmd_paths with current default env or
        set own values.

        make sure that the env has a valid path_resolver
        """
        if cwd is None:
            cwd = self.default_env.get_cwd()
        if cmd_paths is None:
            cmd_paths = self.default_env.get_cmd_paths()
        env = PathManagerEnv(self, cwd, cmd_paths)
        env.resolve()
        log_path.info("created env: %s", env)
        return env

    def parse_config(self, cfg):
        vols_base_dir = cfg.path.vols_base_dir
        if vols_base_dir:
            self.vol_mgr.set_vols_base_dir(vols_base_dir)
        self._parse_auto_volumes(cfg)
        self._parse_auto_assigns(cfg)
        if not self.vol_mgr.parse_config(cfg):
            return False
        if not self.assign_mgr.parse_config(cfg):
            return False
        if not self.default_env.parse_config(cfg):
            return False
        return True

    def _parse_auto_volumes(self, cfg):
        av = cfg.path.auto_volumes
        if av is None:
            av = self.default_auto_volumes
        elif av == ["off"]:
            av = []
        self.auto_volumes = av

    def _parse_auto_assigns(self, cfg):
        aa = cfg.path.auto_assigns
        if aa is None:
            aa = self.default_auto_assigns
        elif aa == ["off"]:
            aa = []
        self.auto_assigns = aa

    def setup(self):
        if not self._add_auto_volumes():
            return False
        if not self._add_auto_assigns():
            return False
        if not self.vol_mgr.setup():
            return False
        if not self.assign_mgr.setup():
            return False
        if not self.validate():
            return False
        self.default_env.resolve()
        self.dump()
        return True

    def _add_auto_volumes(self):
        vm = self.get_vol_mgr()
        am = self.get_assign_mgr()
        # require a default 'system' volume if none is given
        if vm.get_num_volumes() == 0:
            log_path.info("no volume exists: auto adding default 'system:' volume")
            if not vm.add_volume("system:?create"):
                return False
        # run through auto volumes
        for av in self.auto_volumes:
            av = av.lower()
            if not am.is_assign(av) and not vm.is_volume(av):
                if av == "root":
                    spec = "root:/"
                elif av == "ram":
                    spec = "ram:?temp"
                else:
                    log_path.error("invalid auto volume: '%s'", av)
                    return False
                # add auto volume
                log_path.info("auto adding volume: %s", spec)
                if not vm.add_volume(spec):
                    return False
        # done
        return True

    def _add_auto_assigns(self):
        vm = self.get_vol_mgr()
        am = self.get_assign_mgr()
        # setup 'sys:' assign
        if not am.is_assign("sys") and not vm.is_volume("sys"):
            # try to map to system:
            if not am.is_assign("system") and not vm.is_volume("system"):
                log_path.info("no sys: defined: auto adding default 'system:' volume")
                if not vm.add_volume("system:?create"):
                    return False
            spec = "sys:system:"
            if not am.add_assign(spec):
                return False
        # add auto assigns
        for aa in self.auto_assigns:
            aa = aa.lower()
            if not am.is_assign(aa) and not vm.is_volume(aa):
                if aa == "t":
                    vol = "ram"
                else:
                    vol = "sys"
                opt = ""
                if self.auto_assigns_mkdir:
                    opt = "?create"
                spec = "%s:%s:%s%s" % (aa, vol, aa, opt)
                log_path.info("adding auto assign: %s", spec)
                if not am.add_assign(spec):
                    return False
        # done
        return True

    def shutdown(self):
        log_path.info("shutting down paths")
        self.assign_mgr.shutdown()
        self.vol_mgr.shutdown()

    def dump(self):
        self.vol_mgr.dump()
        self.assign_mgr.dump()
        self.default_env.dump()
        log_path.info("---")

    def validate(self):
        return self.validate_assigns()

    def validate_assigns(self):
        assigns = self.assign_mgr.get_all_names()
        for a in assigns:
            try:
                paths = self.assign_mgr.get_assign(a).get_assigns()
                for path in paths:
                    self.volpaths(path, strict=True)
            except AmiPathError as e:
                log_path.error("invalid assign: '%s': %s", a, e)
                return False
        return True

    def get_all_volume_names(self):
        return self.vol_mgr.get_all_names()

    def get_volume(self, vol_name):
        return self.vol_mgr.get_volume(vol_name)

    def get_all_assign_names(self):
        return self.assign_mgr.get_all_names()

    def get_assign(self, assign):
        return self.assign_mgr.get_assign(assign)

    def get_cmd_paths(self):
        return self.default_env.get_cmd_paths()

    def get_cwd(self):
        return self.default_env.get_cwd()

    def is_prefix_valid(self, ami_path):
        """check if prefix is either a volume or assign name

        raise AmiPathError is path is relative
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        p = ami_path.prefix()
        if p is None:
            raise AmiPathError(ami_path, "no prefix in path")
        # check for volume name
        if self.vol_mgr.is_volume(p):
            return True
        # check for assign name
        if self.assign_mgr.is_assign(p):
            return True
        return False

    def is_volume_path(self, ami_path):
        """check if the prefix is a valid volume name.

        raise AmiPathError is path is relative
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        p = ami_path.prefix()
        if p is None:
            raise AmiPathError(ami_path, "no prefix in path")
        # check for volume name
        if self.vol_mgr.is_volume(p):
            return True
        return False

    def is_assign_path(self, ami_path):
        """check if the prefix is a valid assign name.

        raise AmiPathError is path is relative
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        p = ami_path.prefix()
        if p is None:
            raise AmiPathError(ami_path, "no prefix in path")
        # check for assign name
        if self.assign_mgr.is_assign(p):
            return True
        return False

    def is_valid(self, ami_path):
        """check if given path has valid syntax and if its absolute then
        also check prefix"""
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        if not ami_path.is_syntax_valid():
            return False
        if ami_path.is_absolute():
            return self.is_prefix_valid(ami_path)
        else:
            return True

    def is_multi_assign_path(self, ami_path):
        """check if path resolves to multiple paths

        raise AmiPathError is path is relative
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        # expand along assigns until a multi assign or a volume is found
        while True:
            p = ami_path.prefix()
            if p is None:
                raise AmiPathError(ami_path, "no prefix in path")
            # get assign list or None
            a = self.assign_mgr.get_assign(p)
            # no more assign: is volume
            if a is None:
                return False
            # already a multi assign. stop
            alist = a.get_assigns()
            if len(alist) > 1:
                return True
            # resolve single assign as it might ref a multi assign
            else:
                ami_path = AmiPath(alist[0])

    def abspath(self, ami_path, env=None):
        """return an absolute Amiga path

        If the path is already absolute then return path itself.
        Otherwise create a new AmiPath object with the absolute path
        by joining this path with the current directory of the path env.

        An AmiPathError is raised if the relative path cannot be joined
        to the current directory, e.g.:  "foo:".join("/")
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        # already absolute?
        if ami_path.is_absolute():
            log_path.debug("abspath: is_absolute: '%s'", ami_path)
            return ami_path
        # get current directory and join cur dir with my path
        if env is None:
            env = self.default_env
            cwd = env.get_cwd()
        else:
            # make sure its a volume path
            cwd = env.get_cwd()
        res_path = cwd.join(ami_path)
        log_path.debug(
            "abspath: relpath='%s' cwd='%s' -> join '%s'", ami_path, cwd, res_path
        )
        return res_path

    def volpath(self, ami_path, env=None, strict=False):
        """return a volume path.

        Try to resolve a path to a single volume path. If
        assigns are encountered that resolve to multiple paths
        then an AmiPathError is raised.

        If the path has an unknown prefix then return None
        of if 'strict' is True then raise an AmiPathError.

        Raises AmiPathError is relative path is invalid.
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        # if its a local path then simply append cwd
        if ami_path.is_local():
            return self.abspath(ami_path, env)
        # if its already a volume path then keep it
        elif self.is_volume_path(ami_path):
            return ami_path
        # if its an assign path: resolve it
        elif self.is_assign_path(ami_path):
            # resolve assigns
            res_path = self.assign_mgr.resolve_assigns(str(ami_path))
            if type(res_path) is str:
                return AmiPath(res_path)
            else:
                raise AmiPathError(
                    ami_path,
                    "volpath() encountered multi assigns! (%s)" % str(res_path),
                )
        # unknown prefix
        elif strict:
            raise AmiPathError(ami_path, "volpath(): invalid prefix!")
        else:
            return None

    def volpaths(self, ami_path, env=None, strict=False):
        """return a list of volume paths for this path.

        If the path resolves to multiple paths then all resulting paths
        are generated by recursevily applying multi-assigns.

        If the prefix does not exist then return an empty list
        or if strict is True rais an
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        if ami_path.is_local():
            return [self.abspath(ami_path, env)]
        elif self.is_volume_path(ami_path):
            return [ami_path]
        elif self.is_assign_path(ami_path):
            # assigns
            res = self.assign_mgr.resolve_assigns(str(ami_path))
            if type(res) is str:
                return [AmiPath(res)]
            else:
                return [AmiPath(x) for x in res]
        elif strict:
            raise AmiPathError(ami_path, "volpaths(): invalid prefix!")
        else:
            return []

    def resolve_assigns(self, ami_path, recursive=False):
        """if path is prefixed by an assign name then resolve the assign.

        return a list of AmiPaths if mutliple assigns are involved
        or return a single path

        If the path is relative or if the prefix is not an assign then
        path is returned as is.

        Returns a list of AmiPaths if the assign chain resolved to multiple
        paths otherwise a single AmiPath() is returned.
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        if ami_path.is_absolute() and self.is_assign_path(ami_path):
            res = self.assign_mgr.resolve_assigns(str(ami_path), recursive)
            if type(res) is str:
                return AmiPath(res)
            else:
                return [AmiPath(x) for x in res]
        else:
            return ami_path

    def cmdpaths(self, ami_path, env=None, prepend_cur_dir=True, make_volpaths=True):
        """return a list of command paths derived from this path.

        If the path contains a name only then a list containing the
        current cmd paths form the path env are returned. If
        prepend_cur_dir is enabled then the current dir is added as well.

        If this path is not a name only then it is converted to a
        volpath and returned in a single item list.

        Path that do not end with name raise an AmiPathError
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        if ami_path.is_name_only():
            # only a command name is given
            if env is None:
                env = self.default_env
            # get cmd paths
            cmd_paths = env.get_cmd_paths()
            if make_volpaths:
                res = []
                for cp in cmd_paths:
                    res += self.volpaths(cp)
            else:
                res = cmd_paths
            # join our name
            res = list([x.join(ami_path) for x in res])
            # add current dir
            if prepend_cur_dir:
                cur_dir = env.get_cwd()
                res.insert(0, cur_dir.join(ami_path))
            return res
        elif ami_path.ends_with_name():
            # use my path only
            if make_volpaths:
                return self.volpaths(ami_path)
            else:
                return [ami_path]
        else:
            raise AmiPathError(ami_path, "can't derive cmdpaths")

    def to_sys_path(self, ami_path, env=None, strict=False):
        """Convert an Amiga path to a sys path

        If path is not a volume path it will be converted with volpath()
        first.
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        if ami_path.is_local() or not self.is_volume_path(ami_path):
            ami_path = self.volpath(ami_path, env=env, strict=strict)
            if ami_path is None:
                return None
        res = self.vol_mgr.ami_to_sys_path(str(ami_path))
        return res

    def from_sys_path(self, sys_path, strict=False):
        """Convert sys path to AmiPath

        If sys_path is not absolute then resolve it first.

        If path is not mappable return None or
        if strict mode is True then raise an SysPathError
        """
        ami_path = self.vol_mgr.sys_to_ami_path(sys_path)
        if ami_path:
            return AmiPath(ami_path)
        elif strict:
            raise SysPathError(sys_path, "can't map to ami path!")
        else:
            return None

    def resolve_esc_sys_path(self, ami_path, strict=False):
        """resolve an escaped sys path inside an ami path

        An escaped sys path starts with a '::' and an absolute or relative sys
        path. If an escaped path is detected then we try to convert this
        path from sys to ami path and return it.

        Any amiga path is returned untouched.

        If the sys path cannot be resolved then return None
        or raise a SysPathError is strict is True.

        An empty sys path raises an AmiPathError
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        ap = str(ami_path)
        if ap.startswith("::"):
            sys_path = ap[2:]
            if len(sys_path) == 0:
                raise AmiPathError(ami_path, "empty esc sys path!")
            return self.from_sys_path(sys_path, strict)
        else:
            return ami_path
