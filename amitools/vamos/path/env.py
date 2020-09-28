from .amipath import AmiPath, AmiPathError
from .lazypath import LazyPath, LazyPathList
from amitools.vamos.log import log_path


class AmiPathEnv(object):
    def __init__(self, cwd=None, cmd_paths=None):
        if cwd is None:
            cwd = "sys:"
        if cmd_paths is None:
            cmd_paths = ["c:"]
        self.cwd = LazyPath(cwd, self._cmd_path_resolver)
        self.cmd_paths = LazyPathList(cmd_paths, self._cmd_path_resolver)

    def __repr__(self):
        return "AmiPathEnv(cwd=%s, cmd_paths=%s)" % (self.cwd, self.cmd_paths)

    def __str__(self):
        return "[cwd=%s, cmd_paths=%s]" % (self.cwd, self.cmd_paths)

    def __eq__(self, other):
        if not isinstance(other, AmiPathEnv):
            return NotImplemented
        self.resolve()
        other.resolve()
        return self.cwd == other.cwd and self.cmd_paths == other.cmd_paths

    def __ne__(self, other):
        if not isinstance(other, AmiPathEnv):
            return NotImplemented
        self.resolve()
        other.resolve()
        return self.cwd != other.cwd or self.cmd_paths != other.cmd_paths

    def parse_config(self, cfg):
        if cfg is None:
            return True
        path = cfg.path
        if path is None:
            return True
        if path.cwd:
            self.cwd.set(path.cwd)
        if path.command:
            self.cmd_paths.set(path.command)
        return True

    def dump(self):
        log_path.info("--- env ---")
        log_path.info("cwd: %s", self.cwd)
        log_path.info("cmd_paths: %s", self.cmd_paths)

    def is_resolved(self):
        return self.cwd.is_resolved() and self.cmd_paths.is_resolved()

    def is_cwd_resolved(self):
        return self.cwd.is_resolved()

    def are_cmd_paths_resolved(self):
        return self.cmd_paths.is_resolved()

    def resolve(self, force=False):
        if force or not self.cwd.is_resolved():
            self.cwd.resolve()
        if force or not self.cmd_paths.is_resolved():
            self.cmd_paths.resolve()

    def get_cwd(self):
        """get the current working dir as a resolved AmiPath"""
        return self.cwd.get_resolved()

    def set_cwd(self, cwd):
        """set the current working dir as AmiPath or str"""
        self.cwd.set(cwd)

    def get_cwd_lazy_path(self):
        """access internal lazy path instance of cwd"""
        return self.cwd

    def get_cmd_paths(self):
        """return resolved list of command paths"""
        return self.cmd_paths.get_resolved()

    def set_cmd_paths(self, cmd_paths):
        """set a new list of command paths"""
        self.cmd_paths.set(cmd_paths)

    def get_cmd_paths_lazy_path_list(self):
        """access internal lazy path list instance of cmd paths"""
        return self.cmd_paths

    def append_cmd_path(self, path):
        """append a new cmd path"""
        self.cmd_paths.append(path)

    def prepend_cmd_path(self, path):
        """prepend a new cmd path"""
        self.cmd_paths.prepend(path)

    def remove_cmd_path(self, path):
        """remove a cmd path from the list"""
        self.cmd_paths.remove(path)

    def _cwd_path_resolver(self, ami_path):
        """resolve and check cwd"""
        # assume cwd is absolute
        if not ami_path.is_absolute():
            raise AmiPathError(ami_path, "cwd is not absolute!")
        return ami_path

    def _cmd_path_resolver(self, ami_path):
        """resolve and check a command path"""
        # assume cmd path is absolute
        if not ami_path.is_absolute():
            raise AmiPathError(ami_path, "cmd path is not absolute!")
        return ami_path
