"""Host (system) path handling for the vamos path layer.

This module is the boundary between Amiga paths and the host file system.
The Amiga path logic (see :mod:`amipath`, :mod:`env`, :mod:`assign`) does
not touch the host file system. All conversions and host accesses are
bundled here so the host file system handling can later be factored out
of the vamos core.

Naming: a "sys path" is a path in the host file system (e.g. ``/tmp/foo``)
while an "ami path" is an AmigaDOS path (e.g. ``work:foo``).
"""

import os
import os.path
import shutil
from collections import namedtuple

from amitools.vamos.log import log_path
from .amipath import AmiPath, AmiPathError, collapse_parent_steps


DiskUsage = namedtuple("DiskUsage", "total used free block_size read_only")


class SysPathError(Exception):
    def __init__(self, path, reason):
        self.path = path
        self.reason = reason

    def __str__(self):
        return "path='%s': %s" % (self.path, self.reason)


def resolve_sys_path(sys_path):
    """replace ~ (home) or environment variables in path and
    make path absolute

    return resolved path
    """
    # expand system path
    sys_path = os.path.expanduser(sys_path)
    sys_path = os.path.expandvars(sys_path)
    abs_path = os.path.abspath(sys_path)
    return abs_path


class HostFileSystem(object):
    """Wrapper around the host file system operations used by the path layer.

    Keeping these calls behind a single object makes the host dependency
    explicit and allows substituting it later.
    """

    # ----- queries -----

    def is_file(self, sys_path):
        return os.path.isfile(sys_path)

    def is_dir(self, sys_path):
        return os.path.isdir(sys_path)

    def exists(self, sys_path):
        return os.path.exists(sys_path)

    def list_dir(self, sys_path):
        return os.listdir(sys_path)

    # ----- path handling -----

    def join_path(self, base, rel_path):
        if type(rel_path) in (list, tuple):
            rel_path = os.path.join(*rel_path)
        return os.path.join(base, rel_path)

    def ensure_dir(self, sys_path):
        """resolve sys_path and make sure it is an existing directory.

        return the resolved path or None on error
        """
        sys_path = resolve_sys_path(sys_path)
        if self.is_dir(sys_path):
            log_path.debug("found dir: %s", sys_path)
            return sys_path
        log_path.info("creating dir: %s", sys_path)
        if self.make_dir(sys_path):
            return sys_path
        return None

    # ----- directory creation/removal -----

    def make_dir(self, sys_path):
        try:
            # exist_ok: concurrent vamos instances may create shared dirs
            # (e.g. the auto 'system:' volume) between our check and here
            os.makedirs(sys_path, exist_ok=True)
            return True
        except OSError as e:
            log_path.error("error creating dir: %s -> %s", sys_path, e)
            return False

    # ----- file operations -----

    def open(self, sys_path, mode):
        return open(sys_path, mode)

    def stat(self, sys_path):
        return os.stat(sys_path)

    def access(self, sys_path, mode):
        return os.access(sys_path, mode)

    def remove(self, sys_path):
        os.remove(sys_path)

    def rmdir(self, sys_path):
        os.rmdir(sys_path)

    def rename(self, old_path, new_path):
        os.rename(old_path, new_path)

    def chmod(self, sys_path, mode):
        os.chmod(sys_path, mode)

    def mkdir(self, sys_path):
        os.mkdir(sys_path)

    def utime(self, sys_path, times):
        os.utime(sys_path, times)

    def disk_usage(self, sys_path):
        """return a :class:`DiskUsage` with block counts and block size"""
        if hasattr(os, "statvfs"):
            st = os.statvfs(sys_path)
            block_size = st.f_frsize or st.f_bsize
            return DiskUsage(
                st.f_blocks,
                st.f_blocks - st.f_bfree,
                st.f_bfree,
                block_size,
                bool(st.f_flag & os.ST_RDONLY),
            )
        usage = shutil.disk_usage(sys_path)
        block_size = 512
        return DiskUsage(
            usage.total // block_size,
            usage.used // block_size,
            usage.free // block_size,
            block_size,
            False,
        )

    def get_umask(self):
        um = os.umask(0)
        os.umask(um)
        return um


def follow_path_no_case(file_system, base, dirs, fast=False):
    """follow the path components in ``dirs`` below ``base``, correcting the
    case of each existing component to match the host file system.

    Components that are not found are appended as given, so a new path can
    be built for creation. Return the resulting host path.
    """
    # base is the name (no more dirs)
    if len(dirs) == 0:
        return base
    # make sure base is a dir
    if not file_system.is_dir(base):
        # assume remainder is new
        return os.path.join(base, os.path.join(*dirs))
    # dir component to search
    d = dirs[0]
    # check for direct match first
    if fast:
        dp = os.path.join(base, d)
        if file_system.exists(dp):
            return follow_path_no_case(file_system, dp, dirs[1:], fast)
    # read dir and check for no case variant
    dlow = d.lower()
    dl = len(d)
    for f in file_system.list_dir(base):
        if len(f) == dl:
            flow = f.lower()
            if flow == dlow:
                res = os.path.join(base, f)
                return follow_path_no_case(file_system, res, dirs[1:], fast)
    # can't find it -> we assume rest of path is new
    return os.path.join(base, os.path.join(*dirs))


class SysVolume(object):
    """Host file system side of an Amiga volume.

    It owns the host path of a volume and performs all setup, teardown and
    directory creation on it. The Amiga side only refers to the volume by
    name and asks this object for its current host path.
    """

    def __init__(self, name, path, cfg=None, file_system=None):
        if cfg is None:
            cfg = {}
        if file_system is None:
            file_system = HostFileSystem()
        self.name = name
        self.path = path
        self.cfg = cfg
        self.file_system = file_system

    def get_path(self):
        return self.path

    def setup(self):
        path = self.path
        # a non-host handler (nil:, console:, ...) has no host directory
        if path is None:
            return True
        # does path exist?
        if not self.file_system.is_dir(path):
            if "create" in self.cfg:
                log_path.info("creating volume dir: %s", path)
                if not self.file_system.make_dir(path):
                    return False
            else:
                log_path.error("volume path does not exist: '%s'", path)
                return False
        return True

    def shutdown(self):
        # a volume no longer owns host state to release
        pass

    def create_rel_sys_path(self, rel_path):
        if self.path is None:
            # a non-host handler has no host directory to create
            return None
        path = self.file_system.join_path(self.path, rel_path)
        if self.file_system.is_dir(path):
            log_path.debug(
                "rel sys path in volume already exists '%s' + %s -> %s",
                self.name,
                rel_path,
                path,
            )
            return path
        log_path.debug(
            "creating rel sys path in volume '%s' + %s -> %s",
            self.name,
            rel_path,
            path,
        )
        if self.file_system.make_dir(path):
            return path
        log_path.error(
            "error creating rel sys path in volume '%s' + %s -> %s",
            self.name,
            rel_path,
            path,
        )
        return None


class SysPathMapper(object):
    """Map Amiga volume paths to host system paths and back.

    The mapper only translates between the two path models. It does not own
    the volumes but asks the given volume provider for them. A provider has
    to offer ``get_all_volumes()`` and ``get_volume(name)``.
    """

    def __init__(self, vol_provider, file_system=None):
        self.vol_provider = vol_provider
        if file_system is None:
            file_system = HostFileSystem()
        self.file_system = file_system

    def sys_to_ami_path(self, sys_path):
        """try to map an absolute system path back to an amiga path

        if multiple volumes overlap then take the shortest amiga path

        return ami_path or None if sys_path can't be mapped
        """
        if not os.path.isabs(sys_path):
            sys_path = resolve_sys_path(sys_path)
            log_path.debug("vol: sys_to_ami_path: resolved rel path: %s", sys_path)
        res_len = None
        result = None
        for volume in self.vol_provider.get_all_volumes():
            vol_sys_path = volume.get_path()
            # a non-host handler (nil:, console:, ...) has no host path
            if vol_sys_path is None:
                continue
            try:
                common_path = os.path.commonpath([vol_sys_path, sys_path])
            except ValueError:
                continue
            if os.path.normcase(common_path) == os.path.normcase(
                os.path.normpath(vol_sys_path)
            ):
                remainder = os.path.relpath(sys_path, vol_sys_path)
                if remainder == os.curdir:
                    remainder = ""
                n = len(remainder)
                # get volume name and build amiga path
                vol_name = volume.get_name()
                ami_path = vol_name + ":" + remainder
                log_path.debug(
                    "vol: sys_to_ami_path: sys='%s' -> ami='%s'", sys_path, ami_path
                )
                if result is None or n < res_len:
                    result = ami_path
                    res_len = n
        # return best result
        log_path.info("vol: sys_to_ami_path: sys='%s' -> ami=%s", sys_path, result)
        return result

    def ami_to_sys_path(self, ami_path, fast=False):
        """Map an Amiga path to a system path.

        An absolute Amiga path with volume prefix is expected.
        Any other path returns None.

        If volume does not exist also return None.

        It replaces the volume with the sys_path prefix.
        Furthermore, the remaining Amiga path is mapped to
        the system file system and case corrected if a
        corresponding entry is found.

        If 'fast' mode is enabled then the original case
        of the path elements is kept if the underlying FS
        is case insensitive.

        Return None on error or system path
        """
        # find volume
        pos = ami_path.find(":")
        if pos <= 0:
            log_path.debug("vol: ami_to_sys_path: empty volume: %s", ami_path)
            return None
        vol_name = ami_path[:pos].lower()
        # check volume name
        volume = self.vol_provider.get_volume(vol_name)
        if volume is not None:
            vol_sys_path = volume.get_path()
            # a non-host handler (nil:, console:, ...) has no host path
            if vol_sys_path is None:
                return None
            remainder = ami_path[pos + 1 :]

            # only volume name given
            if len(remainder) == 0:
                log_path.info(
                    "vol: direct volume: ami='%s' -> sys='%s'", ami_path, vol_sys_path
                )
                return vol_sys_path

            # invalid volume:/... path
            if remainder[0] == "/":
                log_path.error("vol: ami_to_sys_path: invalid :/ path: %s", ami_path)
                return None

            # follow ami path along in sys world
            dirs = collapse_parent_steps(remainder.split("/"))
            if dirs is None:
                log_path.error(
                    "vol: ami_to_sys_path: parent step above volume: %s", ami_path
                )
                return None
            sys_path = self._follow_path_no_case(vol_sys_path, dirs, fast)
            log_path.info(
                "vol: ami_to_sys_path: ami='%s' -> sys='%s'", ami_path, sys_path
            )
            return sys_path
        else:
            log_path.error(
                "vol: ami_to_sys_path: volume='%s' not found: %s", vol_name, ami_path
            )
            return None

    def _follow_path_no_case(self, base, dirs, fast):
        return follow_path_no_case(self.file_system, base, dirs, fast)


class SysPathResolver(object):
    """Convert Amiga paths to host paths (and back) for a path manager.

    All Amiga side resolution (assigns, cwd, volume prefixes) is delegated
    to the given path manager. The actual host mapping is done by the
    volume manager's :class:`SysPathMapper`.
    """

    def __init__(self, path_mgr, vol_mgr=None, file_system=None):
        self.path_mgr = path_mgr
        if vol_mgr is None:
            vol_mgr = path_mgr.get_vol_mgr()
        self.vol_mgr = vol_mgr
        if file_system is None:
            # share the host file system with the volume's sys path mapper
            file_system = vol_mgr.get_sys_path_mapper().file_system
        self.file_system = file_system

    def to_sys_path(self, ami_path, env=None, strict=False):
        """Convert an Amiga path to a sys path

        If path is not a volume path it will be converted with volpath()
        first.
        """
        if type(ami_path) is str:
            ami_path = AmiPath(ami_path)
        if ami_path.is_local() or not self.path_mgr.is_volume_path(ami_path):
            ami_path = self.path_mgr.volpath(ami_path, env=env, strict=strict)
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
