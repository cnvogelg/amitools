"""Map a native handler config to a block device and its geometry.

A real AmigaDOS file system handler does not read files: it opens a *block
device* (``scsi.device``) and applies the partition geometry from its
``DosEnvec``. This module turns the handler config into the pieces the startup
message needs:

* the device name (``scsi.device`` by default) and the unit number;
* the geometry source (the ``DosEnvec`` of an RDB partition) for
  :func:`~amitools.vamos.handler.native.startup.build_startup`.

RDB-first: the geometry is taken from the ``DiskSession`` that already
installed ``scsi.device``. A plain ADF/HDF (no RDB) falls back to a small
synthetic geometry so the handler still starts; the raw whole-disk backend is
a later step (HANDLER.md step 25).
"""

DEFAULT_DEVICE = "scsi.device"


class BlkDevGeometry:
    """synthetic ``DosEnvec`` source for a handler without a real partition

    The values describe a small, valid volume so a handler that trusts the
    geometry starts without reading past the disk.
    """

    size = 16
    block_size = 128  # de_SizeBlock is in longwords: 128 * 4 = 512 bytes
    sec_org = 0
    surfaces = 2
    sec_per_blk = 1
    blk_per_trk = 11
    reserved = 2
    pre_alloc = 0
    interleave = 0
    low_cyl = 0
    high_cyl = 79
    num_buffer = 30
    buf_mem_type = 0
    max_transfer = 0x7FFFFFFF
    mask = 0x7FFFFFFE
    boot_pri = 0
    dos_type = 0x444F5300  # 'DOS\0'
    baud = 0
    control = 0
    boot_blocks = 0


class BlkDevSpec:
    """the block device a native handler is bound to"""

    def __init__(self, device, unit, geometry):
        self.device = device
        self.unit = unit
        self.geometry = geometry

    def __repr__(self):
        return "BlkDevSpec(device=%s, unit=%s, geometry=%s)" % (
            self.device,
            self.unit,
            type(self.geometry).__name__,
        )


def _find_partition(disk_session, part):
    """find ``part`` (name or index) across the session's disk units"""
    for unit in disk_session.get_units():
        backend = disk_session.get_backend(unit)
        partitions = getattr(backend, "partitions", ())
        for partition in partitions:
            name = partition.name.rstrip(":")
            if part == name or str(part) == str(partition.index):
                return unit, partition.dos_env
    return None, None


def resolve_blkdev(disk_session, config):
    """build a :class:`BlkDevSpec` from a ``NativeConfig``

    A partition that can be resolved in the disk session supplies both the unit
    and the geometry; otherwise a synthetic geometry is used.
    """
    device = config.device or DEFAULT_DEVICE
    unit = config.unit
    part = config.part

    geometry = None
    if disk_session is not None and part is not None:
        found_unit, found_geometry = _find_partition(disk_session, part)
        if found_geometry is not None:
            geometry = found_geometry
            if unit is None:
                unit = found_unit
    if geometry is None:
        geometry = BlkDevGeometry()
    if unit is None:
        unit = 0
    return BlkDevSpec(device, unit, geometry)
