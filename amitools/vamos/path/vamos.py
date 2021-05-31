import os.path
import os
from amitools.vamos.log import log_path
from .mgr import PathManager
from .amipath import AmiPath, AmiPathError


class VamosPathManager(PathManager):
    """The VamosPathManager keeps the old vamos path manager API (for now)
    but has already the new PathManager under the hood.
    """

    def _get_lock_env(self, lock):
        cmd_paths = self.get_default_env().get_cmd_paths()
        if lock is None:
            cwd = "sys:"
        else:
            cwd = lock.ami_path
        cwd = AmiPath(cwd)
        return self.create_env(cwd=cwd, cmd_paths=cmd_paths)

    # ----- API -----

    def ami_command_to_sys_path(self, cwd_lock, ami_path):
        """lookup a command on path if it does not contain a relative or
        absolute path. otherwise perform normal 'ami_to_sys_path' conversion"""
        env = self._get_lock_env(cwd_lock)
        cmd_paths = self.cmdpaths(ami_path, env=env)
        log_path.info(
            "ami_command_to_sys_path: ami_path=%s -> cmd_paths=%s",
            ami_path,
            ",".join(map(str, cmd_paths)),
        )
        # check if ami path exists as sys path
        for cmd_path in cmd_paths:
            sys_path = self.to_sys_path(str(cmd_path))
            if os.path.isfile(sys_path):
                log_path.info(
                    "ami_command_to_sys_path: ami_path=%s -> sys_path=%s, ami_path=%s",
                    ami_path,
                    sys_path,
                    cmd_path,
                )
                return sys_path, cmd_path
        # nothing found
        log_path.info("ami_command_to_sys_path: ami_path='%s' not found!", ami_path)
        return None, None

    def ami_to_sys_path(self, cwd_lock, ami_path, searchMulti=False, mustExist=False):
        env = self._get_lock_env(cwd_lock)
        paths = self.volpaths(ami_path, env=env)
        if len(paths) == 0:
            log_path.info("ami_to_sys_path: ami_path='%s' -> None")
            return None
        # now we have paths with volume:abs/path
        sys_path = None
        # search for existing multi assign
        if searchMulti or mustExist:
            for npath in paths:
                # first try to find existing path in all locations
                spath = self.to_sys_path(str(npath))
                if spath and os.path.exists(spath):
                    sys_path = spath
                    break
        # nothing found -> try first path
        if sys_path is None and not mustExist:
            sys_path = self.to_sys_path(str(paths[0]))
        log_path.info(
            "ami_to_sys_path: ami_path='%s'" " -> volpaths=%s -> sys_path='%s'",
            ami_path,
            ",".join(map(str, paths)),
            sys_path,
        )
        return sys_path

    def sys_to_ami_path(self, sys_path):
        ami_path = self.from_sys_path(sys_path)
        log_path.info(
            "sys_to_ami_path: sys_path='%s' -> abs_path='%s' " "-> ami_path='%s'",
            sys_path,
            ami_path,
        )
        return ami_path

    def ami_abs_parent_path(self, path):
        """return absolute parent path of given path or same if already parent"""
        ami_path = self.volpath(AmiPath(path))
        parent = ami_path.parent()
        if parent is None:
            parent = ami_path
        log_path.info("ami_abs_parent_path: path='%s' -> parent='%s", path, parent)
        return str(parent)

    def ami_abs_path(self, cwd_lock, path):
        """return absolute amiga path from given path"""
        env = self._get_lock_env(cwd_lock)
        abs_path = self.abspath(path, env=env)
        log_path.info("ami_abs_path: path='%s' -> abs_path='%s'", path, abs_path)
        return str(abs_path)

    # ---- path components -----

    def ami_name_of_path(self, cwd_lock, path):
        env = self._get_lock_env(cwd_lock)
        abs_path = self.abspath(path, env=env)
        name = abs_path.filename()
        if name is None:
            name = abs_path.prefix() + ":"
        log_path.info("ami_name_of_path: path='%s' -> name='%s'", path, name)
        return name

    def ami_dir_of_path(self, cwd_lock, path):
        env = self._get_lock_env(cwd_lock)
        abs_path = self.abspath(path, env=env)
        abs_dir = abs_path.absdirname()
        log_path.info("ami_dir_of_path: path='%s' -> dir='%s'", path, abs_dir)
        return abs_dir

    def ami_volume_of_path(self, path):
        ami_path = AmiPath(path)
        p = ami_path.prefix()
        if p is None:
            log_path.error("ami_volume_of_path: expect absolute path: '%s'", path)
            return None
        else:
            log_path.info("ami_volume_of_path: path='%s' -> volume='%s'", path, p)
            return p

    def ami_voldir_of_path(self, cwd_lock, path):
        env = self._get_lock_env(cwd_lock)
        vol_path = self.volpath(path, env=env)
        voldir = vol_path.absdirname()
        log_path.info("ami_voldir_of_path: path='%s' -> voldir='%s'", path, voldir)
        return voldir

    # ----- list dir -----

    def ami_list_dir(self, cwd_lock, ami_path):
        sys_path = self.ami_to_sys_path(cwd_lock, ami_path, mustExist=True)
        if sys_path is None:
            return None
        if not os.path.isdir(str(sys_path)):
            return None
        files = os.listdir(str(sys_path))
        log_path.info(
            "ami_list_dir: path='%s' -> sys_path='%s' -> files=%s",
            ami_path,
            sys_path,
            files,
        )
        return files

    def ami_path_exists(self, cwd_lock, ami_path):
        sys_path = self.ami_to_sys_path(cwd_lock, ami_path, mustExist=True)
        exists = os.path.exists(str(sys_path))
        log_path.info(
            "ami_path_exists: path='%s' -> sys_path='%s' -> exists=%s",
            ami_path,
            sys_path,
            exists,
        )
        return exists

    def ami_path_join(self, a, b):
        return AmiPath(a).join(AmiPath(b))
