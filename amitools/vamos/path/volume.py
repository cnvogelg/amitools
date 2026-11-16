from amitools.vamos.log import log_path
from .spec import Spec
from .syspath import SysPathMapper, SysVolume, HostFileSystem, resolve_sys_path


class Volume(object):
    """Amiga side of a volume.

    The host file system handling is delegated to a :class:`SysVolume`.
    """

    def __init__(self, name, path, cfg=None, file_system=None):
        if cfg is None:
            cfg = {}
        self.name = name
        self.lo_name = name.lower()
        self.cfg = cfg
        self.is_setup = False
        self.sys_volume = SysVolume(name, path, cfg, file_system)

    def __str__(self):
        return "Volume(%s(%s):%s,cfg=%r,is_setup=%s)" % (
            self.name,
            self.lo_name,
            self.get_path(),
            self.cfg,
            self.is_setup,
        )

    def get_name(self):
        """return volume name in original lo/up case writing"""
        return self.name

    def get_path(self):
        """return mapped volume path in original format"""
        return self.sys_volume.get_path()

    def get_lo_name(self):
        """return normalized volume name in lower case"""
        return self.lo_name

    def get_cfg(self):
        """return volume configuration"""
        return self.cfg

    def get_sys_volume(self):
        return self.sys_volume

    def setup(self):
        return self.sys_volume.setup()

    def shutdown(self):
        self.sys_volume.shutdown()

    def create_rel_sys_path(self, rel_path):
        return self.sys_volume.create_rel_sys_path(rel_path)


class VolumeManager(object):
    def __init__(self, vols_base_dir=None, file_system=None):
        if file_system is None:
            file_system = HostFileSystem()
        self.file_system = file_system
        self.volumes = []
        self.is_setup = False
        self.vols_by_name = {}
        self.vols_base_dir = vols_base_dir
        self.sys_path_mapper = SysPathMapper(self, file_system)

    def get_num_volumes(self):
        return len(self.volumes)

    def get_all_volumes(self):
        return self.volumes

    def get_sys_path_mapper(self):
        return self.sys_path_mapper

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
        handler_type = cfg.get("handler", "hostfs")
        n = len(src_list)
        if n == 0:
            if handler_type != "hostfs":
                # a non-host handler (nil:, console:, ...) has no host
                # directory of its own
                path = None
                log_path.debug("non-host handler '%s': no host path", handler_type)
            else:
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
        return Volume(name, path, cfg, self.file_system)

    def _get_local_vol_path(self, name):
        base_dir = self._setup_base_dir()
        if base_dir is None:
            return None
        return self.file_system.join_path(base_dir, name)

    def _setup_base_dir(self):
        # ensure that vols_base_dir exists
        base_dir = self.vols_base_dir
        if not base_dir:
            raise ValueError("volume manager: no base dir given!")
        return self.file_system.ensure_dir(base_dir)

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
        return self.sys_path_mapper.sys_to_ami_path(sys_path)

    def ami_to_sys_path(self, ami_path, fast=False):
        """Map an Amiga path to a system path.

        An absolute Amiga path with volume prefix is expected.
        Any other path returns None.

        If volume does not exist also return None.

        See :meth:`SysPathMapper.ami_to_sys_path` for details.
        """
        return self.sys_path_mapper.ami_to_sys_path(ami_path, fast)
