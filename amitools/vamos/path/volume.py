import os
import os.path
import shutil
from amitools.vamos.log import log_path
import logging
from .spec import Spec


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


class Volume(object):
    def __init__(self, name, path, cfg=None):
        if cfg is None:
            cfg = {}
        self.name = name
        self.path = path
        self.lo_name = name.lower()
        self.cfg = cfg
        self.is_setup = False

    def __str__(self):
        return "Volume(%s(%s):%s,cfg=%r,is_setup=%s)" % (
            self.name,
            self.lo_name,
            self.path,
            self.cfg,
            self.is_setup,
        )

    def get_name(self):
        """return volume name in original lo/up case writing"""
        return self.name

    def get_path(self):
        """return mapped volume path in original format"""
        return self.path

    def get_lo_name(self):
        """return normalized volume name in lower case"""
        return self.lo_name

    def get_cfg(self):
        """return volume configuration"""
        return self.cfg

    def setup(self):
        path = self.path
        # temp dir?
        if "temp" in self.cfg:
            if not self._create_temp(path):
                return False
        # does path exist?
        elif not os.path.isdir(path):
            if "create" in self.cfg:
                if not self._create_path(path):
                    return False
            else:
                log_path.error("volume path does not exist: '%s'", path)
                return False
        return True

    def shutdown(self):
        if "temp" in self.cfg:
            self._delete_temp(self.path)

    def _create_temp(self, path):
        if os.path.exists(path):
            log_path.error("temp volume volume path already exists: '%s'", path)
            return False
        # create temp dir
        try:
            log_path.debug("creating temp dir: %s", path)
            os.makedirs(path)
            return True
        except OSError:
            log_path.error("error creating temp dir: '%s'", path)
            return False

    def _delete_temp(self, path):
        try:
            log_path.debug("removing temp dir: %s", path)
            shutil.rmtree(path)
        except:
            log_path.error("error removing temp dir: '%s'", path)

    def _create_path(self, path):
        # try to create path
        try:
            log_path.info("creating volume dir: %s", path)
            os.makedirs(path)
            return path
        except OSError as e:
            log_path.error("error creating volume dir: %s -> %s", path, e)
            return None

    def create_rel_sys_path(self, rel_path):
        if type(rel_path) in (list, tuple):
            rel_path = os.path.join(*rel_path)
        dir_path = os.path.join(self.path, rel_path)
        if os.path.isdir(dir_path):
            log_path.debug(
                "rel sys path in volume already exists '%s' + %s -> %s",
                self.name,
                rel_path,
                dir_path,
            )
            return dir_path
        try:
            log_path.debug(
                "creating rel sys path in volume '%s' + %s -> %s",
                self.name,
                rel_path,
                dir_path,
            )
            os.makedirs(dir_path)
            return dir_path
        except OSError as e:
            log_path.error(
                "error creating rel sys path in volume '%s' + %s -> %s",
                self.name,
                rel_path,
                dir_path,
            )
            return None


class VolumeManager(object):
    def __init__(self, vols_base_dir=None):
        self.volumes = []
        self.is_setup = False
        self.vols_by_name = {}
        self.vols_base_dir = vols_base_dir

    def get_num_volumes(self):
        return len(self.volumes)

    def set_vols_base_dir(self, dir):
        self.vols_base_dir = dir

    def parse_config(self, cfg):
        if cfg is None:
            return True
        vols = cfg.volumes
        if vols is None:
            return True
        if self.add_volumes(vols) is False:
            return False
        return True

    def dump(self):
        log_path.info("--- volume config ---")
        for volume in self.volumes:
            log_path.info("%s", volume)

    def setup(self):
        # setup all defined volumes
        log_path.debug("setting up volumes")
        for volume in self.volumes:
            if not volume.setup():
                log_path.error("Error settign up volume: %s", volume)
                return False
            volume.is_setup = True
        self.is_setup = True
        return True

    def shutdown(self):
        # shutdown all volumes
        log_path.debug("shutting down volumes")
        for volume in self.volumes:
            log_path.info("cleaning up volume: %s", volume)
            volume.shutdown()
            volume.is_setup = False

    def add_volumes(self, volumes):
        if not volumes:
            return []
        res = []
        for volume in volumes:
            vol = self.add_volume(volume)
            if not vol:
                return False
            res.append(vol)
        return res

    def add_volume(self, spec):
        # get volume for spec
        volume = self._parse_spec(spec)
        if volume is None:
            log_path.error("invalid volume spec: '%s'", spec)
            return None

        # check if volume name already exists?
        lo_name = volume.get_lo_name()
        if lo_name in self.vols_by_name:
            # after setup do not allow duplicate volumes
            if self.is_setup:
                log_path.error("duplicate volume name: '%s'", volume.get_name())
                return None
            # before setup simply overwrite existing volume
            else:
                old_volume = self.vols_by_name[lo_name]
                log_path.info("overwriting volume: %s", old_volume)
                self.volumes.remove(old_volume)
                del self.vols_by_name[lo_name]

        # after global setup try to setup volume immediately
        if self.is_setup:
            if not volume.setup():
                log_path.error("error setting up volume: %s", volume)
                return None
            volume.is_setup = True

        # finally add volume
        log_path.info("adding volume: %s", volume)
        self.vols_by_name[lo_name] = volume
        self.volumes.append(volume)
        return volume

    def _parse_spec(self, spec):
        # auto parse string spec
        if type(spec) is str:
            try:
                spec = Spec.parse(spec)
            except ValueError as e:
                log_path.error("error parsing spec: %r -> %s", spec, e)
                return None
        # check spec
        name = spec.get_name()
        src_list = spec.get_src_list()
        cfg = spec.get_cfg()
        n = len(src_list)
        if n == 0:
            # local path
            path = self._get_local_vol_path(name)
            log_path.debug("local path='%s'", path)
            if path is None:
                return None
        elif n == 1:
            path = resolve_sys_path(src_list[0])
            log_path.debug("resolved path='%s'", path)
        if n > 1:
            log_path.error("only one source in volume spec allowed!")
            return None
        log_path.debug("name='%s', path='%s'", name, path)
        # create volume
        return Volume(name, path, cfg)

    def _get_local_vol_path(self, name):
        base_dir = self._setup_base_dir()
        if base_dir is None:
            return None
        return os.path.join(base_dir, name)

    def _setup_base_dir(self):
        # ensure that vols_base_dir exists
        base_dir = self.vols_base_dir
        if not base_dir:
            raise ValueError("volume manager: no base dir given!")
        base_dir = resolve_sys_path(base_dir)
        if not os.path.isdir(base_dir):
            try:
                log_path.info("creating volume base dir: %s", base_dir)
                os.makedirs(base_dir)
            except OSError as e:
                log_path.error("error creating volume base dir: %s -> %s", base_dir, e)
                return None
        else:
            log_path.debug("found base dir: %s", base_dir)
        return base_dir

    def del_volume(self, name):
        lo_name = name.lower()
        if lo_name not in self.vols_by_name:
            return False
        volume = self.vols_by_name[lo_name]
        volume.shutdown()
        volume.is_setup = False
        self.volumes.remove(volume)
        del self.vols_by_name[lo_name]
        log_path.info("delete volume: %s", volume)
        return True

    def is_volume(self, name):
        return name.lower() in self.vols_by_name

    def get_volume(self, name):
        lo_name = name.lower()
        if lo_name in self.vols_by_name:
            return self.vols_by_name[lo_name]

    def get_all_names(self):
        return [x.get_name() for x in self.volumes]

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
        for volume in self.volumes:
            vol_sys_path = volume.get_path()
            cp = os.path.commonprefix([vol_sys_path, sys_path])
            if cp == vol_sys_path:
                remainder = sys_path[len(vol_sys_path) :]
                n = len(remainder)
                if n > 0 and remainder[0] == "/":
                    remainder = remainder[1:]
                    n -= 1
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
        if vol_name in self.vols_by_name:
            volume = self.vols_by_name[vol_name]
            vol_sys_path = volume.get_path()
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
            dirs = remainder.split("/")
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
        # base is the name (no more dirs)
        if len(dirs) == 0:
            return base
        # make sure base is a dir
        if not os.path.isdir(base):
            # assume remainder is new
            return os.path.join(base, os.path.join(*dirs))
        # dir component to search
        d = dirs[0]
        # check for direct match first
        if fast:
            dp = os.path.join(base, d)
            if os.path.exists(dp):
                return self._follow_path_no_case(dp, dirs[1:], fast)
        # read dir and check for no case variant
        dlow = d.lower()
        files = os.listdir(base)
        dl = len(d)
        for f in files:
            if len(f) == dl:
                flow = f.lower()
                if flow == dlow:
                    res = os.path.join(base, f)
                    return self._follow_path_no_case(res, dirs[1:], fast)
        # can't find it -> we assume rest of path is new
        return os.path.join(base, os.path.join(*dirs))
