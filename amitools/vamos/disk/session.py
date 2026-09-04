"""Lifecycle and DOS registration for disk images exposed by vamos."""

from dataclasses import dataclass

from amitools.vamos.libstructs import DosEnvecStruct, FileSysStartupMsgStruct

from .backend import DiskImage


@dataclass
class _DiskUnit:
    unit: int
    backend: object
    owned: bool
    is_open: bool = False


@dataclass
class _DosDeviceResources:
    dos_list: object
    entry: object
    env: object
    startup: object
    device_name: object


def _set_field(struct, name, value):
    field = getattr(struct, name)
    if hasattr(field, "val"):
        field.val = value
    elif hasattr(field, "aptr"):
        field.aptr = value
    elif hasattr(field, "bptr"):
        field.bptr = value
    else:
        field.set(value)


class DiskSession:
    """Own the disk resources associated with one vamos invocation."""

    def __init__(
        self,
        images=None,
        *,
        read_only=True,
        debug=False,
        acknowledge_read_only_writes=False,
        acknowledge_unsupported_commands=False,
    ):
        self.default_read_only = read_only
        self.debug = debug
        self.acknowledge_read_only_writes = acknowledge_read_only_writes
        self.acknowledge_unsupported_commands = acknowledge_unsupported_commands
        self._units = {}
        self._dos_resources = []
        self._dos_impl = None
        self._installed = False
        if images:
            for image in images:
                self.add_image(image)

    @classmethod
    def from_config(cls, cfg, *, debug=False):
        if cfg is None:
            images = []
        elif isinstance(cfg, dict):
            images = cfg.get("disks", [])
        else:
            images = getattr(cfg, "disks", [])
        return cls(images, read_only=True, debug=debug)

    def _next_unit(self):
        unit = 0
        while unit in self._units:
            unit += 1
        return unit

    def add_image(
        self,
        image,
        *,
        read_only=None,
        block_size=None,
        unit=None,
    ):
        if read_only is None:
            read_only = self.default_read_only
        backend = DiskImage(
            image,
            read_only=read_only,
            block_size=block_size,
        )
        return self.add_backend(backend, unit=unit, owned=True)

    def add_backend(self, backend, *, unit=None, owned=False):
        if unit is None:
            unit = self._next_unit()
        if unit < 0:
            raise ValueError("disk unit must not be negative")
        if unit in self._units:
            raise ValueError("disk unit %d is already configured" % unit)
        self._units[unit] = _DiskUnit(unit, backend, owned)
        return unit

    def set_backend(self, unit, backend, *, owned=False):
        old = self._units.get(unit)
        if old is not None and old.owned and old.is_open and old.backend is not backend:
            old.backend.close()
        self._units[unit] = _DiskUnit(unit, backend, owned)

    def get_backend(self, unit):
        disk_unit = self._units.get(unit)
        return disk_unit.backend if disk_unit is not None else None

    def get_units(self):
        return tuple(sorted(self._units))

    def open(self):
        opened = []
        try:
            for unit in self.get_units():
                disk_unit = self._units[unit]
                if disk_unit.owned and not disk_unit.is_open:
                    disk_unit.backend.open()
                    disk_unit.is_open = True
                    opened.append(disk_unit)
        except Exception:
            for disk_unit in reversed(opened):
                disk_unit.backend.close()
                disk_unit.is_open = False
            raise
        return self

    def install_devices(self, setup_lib_manager, device="scsi.device"):
        """Register this session with an initialized SetupLibManager."""
        from amitools.vamos.lib.ScsiDevice import ScsiDevice

        if self._installed:
            raise RuntimeError("disk devices are already installed")
        setup_lib_manager.lib_mgr.add_impl_cls(
            device, lambda: ScsiDevice(self, debug=self.debug)
        )
        self._installed = True

    def _alloc_dos_env(self, alloc, source):
        env = alloc.alloc_astruct(DosEnvecStruct, label="DosEnvec")
        values = {
            "de_TableSize": getattr(source, "size", 0) or 16,
            "de_SizeBlock": source.block_size,
            "de_SecOrg": source.sec_org,
            "de_Surfaces": source.surfaces,
            "de_SectorPerBlock": source.sec_per_blk,
            "de_BlocksPerTrack": source.blk_per_trk,
            "de_Reserved": source.reserved,
            "de_PreAlloc": source.pre_alloc,
            "de_Interleave": source.interleave,
            "de_LowCyl": source.low_cyl,
            "de_HighCyl": source.high_cyl,
            "de_NumBuffers": source.num_buffer,
            "de_BufMemType": source.buf_mem_type,
            "de_MaxTransfer": source.max_transfer,
            "de_Mask": source.mask,
            "de_BootPri": source.boot_pri,
            "de_DosType": source.dos_type,
            "de_Baud": source.baud,
            "de_Control": source.control,
            "de_BootBlocks": source.boot_blocks,
        }
        for name, value in values.items():
            _set_field(env, name, value)
        return env

    def _alloc_startup(self, alloc, unit, env, device):
        device_name = alloc.alloc_bstr(device, label="DiskDeviceName")
        startup = None
        try:
            startup = alloc.alloc_astruct(
                FileSysStartupMsgStruct, label="FileSysStartupMsg"
            )
            _set_field(startup, "fssm_Unit", unit)
            _set_field(startup, "fssm_Device", device_name.addr)
            _set_field(startup, "fssm_Environ", env.addr)
            _set_field(startup, "fssm_Flags", 0)
            return startup, device_name
        except Exception:
            if startup is not None:
                startup.free()
            alloc.free_bstr(device_name)
            raise

    def install_dos(self, dos_impl, device="scsi.device"):
        """Register every RDB partition as a DLT_DEVICE entry."""
        if self._dos_resources:
            raise RuntimeError("DOS disk devices are already installed")
        alloc = dos_impl.alloc
        dos_list = dos_impl.dos_list
        self._dos_impl = dos_impl
        try:
            for unit in self.get_units():
                backend = self.get_backend(unit)
                for partition in getattr(backend, "partitions", ()):
                    name = partition.name.rstrip(":")
                    if dos_list.get_entry_by_name(name) is not None:
                        raise ValueError("duplicate DOS device name: %s" % name)
                    env = self._alloc_dos_env(alloc, partition.dos_env)
                    startup = None
                    device_name = None
                    try:
                        startup, device_name = self._alloc_startup(
                            alloc, unit, env, device
                        )
                        entry = dos_list.add_device(
                            name,
                            startup.addr >> 2,
                            task=0,
                            exclusive=bool(getattr(backend, "exclusive", False)),
                            unit=unit,
                        )
                    except Exception:
                        if startup is not None:
                            startup.free()
                        env.free()
                        if device_name is not None:
                            alloc.free_bstr(device_name)
                        raise
                    self._dos_resources.append(
                        _DosDeviceResources(dos_list, entry, env, startup, device_name)
                    )
            dos_impl.update_dos_list_head()
        except Exception:
            self.release_dos(dos_impl)
            raise

    def release_dos(self, dos_impl=None):
        if dos_impl is None:
            dos_impl = self._dos_impl
        for resources in reversed(self._dos_resources):
            # The session owns these allocations even if another caller
            # has already detached the node from the maintained DOS list.
            resources.dos_list.remove_entry(resources.entry)
            resources.dos_list.free_entry(resources.entry)
            resources.startup.free()
            resources.env.free()
            alloc = getattr(dos_impl, "alloc", None)
            if alloc is None:
                alloc = resources.dos_list.alloc
            alloc.free_bstr(resources.device_name)
        self._dos_resources = []
        if dos_impl is not None:
            dos_impl.update_dos_list_head()
        self._dos_impl = None

    def close(self):
        first_error = None
        try:
            self.release_dos()
        except Exception as exc:
            first_error = exc
        for unit in reversed(self.get_units()):
            disk_unit = self._units[unit]
            if not disk_unit.owned or not disk_unit.is_open:
                continue
            try:
                disk_unit.backend.close()
            except Exception as exc:
                if first_error is None:
                    first_error = exc
            finally:
                disk_unit.is_open = False
        if first_error is not None:
            raise first_error
