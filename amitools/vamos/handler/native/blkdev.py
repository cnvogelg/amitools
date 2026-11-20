"""Map a native handler config to a block device and its geometry.

A real AmigaDOS file system handler does not read files: it opens a *block
device* (``scsi.device``) and applies the partition geometry from its
``DosEnvec``. This module turns the handler config into the pieces the startup
message needs:

* the block device (``scsi.device``) and the unit number;
* the geometry source (the ``DosEnvec`` of an RDB partition) for
  :func:`~amitools.vamos.handler.native.startup.build_startup`.

The partition is referenced through a :class:`~amitools.vamos.disk.DiskSession`
(HANDLER.md step 24b): ``device`` names the DOS device node (``DH0``) that
``DiskSession.install_dos`` created for a partition, ``part`` names the RDB
partition directly (by name or index). With neither set the volume name is
tried, and the first partition is the final fallback. The geometry comes from
``DiskSession.get_backend(unit).partitions[...]``, which is available once
``disk_session.open()`` ran, so the manager does not depend on the DOS list.

RDB-first: a native handler mounts an RDB partition. A raw ADF/HDF is now
exposed as a whole-disk ``--disk`` device (HANDLER.md step 25), but binding a
native handler to that raw device is a separate step, so a handler with no RDB
partition still falls back to a small synthetic geometry.
"""

from amitools.vamos.log import log_handler

# the block device a started handler opens with OpenDevice()
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

    def __init__(
        self,
        device,
        unit,
        geometry,
        partition_name=None,
        driver_data=None,
        driver_globvec=None,
    ):
        self.device = device
        self.unit = unit
        self.geometry = geometry
        # the RDB partition's DOS device name (e.g. ``DH0``), when resolved;
        # lets the manager reuse that node's ``FileSysStartupMsg`` (step 24c)
        self.partition_name = partition_name
        # the RDB driver for the partition (seglist data, globvec); a handler
        # without an explicit ``binary=`` loads it (step 24d)
        self.driver_data = driver_data
        self.driver_globvec = driver_globvec

    def __repr__(self):
        return "BlkDevSpec(device=%s, unit=%s, geometry=%s)" % (
            self.device,
            self.unit,
            type(self.geometry).__name__,
        )


def _find_partition(disk_session, selector):
    """find a partition by DOS device name or RDB index across the units

    Returns ``(unit, partition)`` or ``None``.
    """
    if selector is None:
        return None
    for unit in disk_session.get_units():
        backend = disk_session.get_backend(unit)
        for partition in getattr(backend, "partitions", ()):
            name = partition.name.rstrip(":")
            if selector == name or str(selector) == str(partition.index):
                return unit, partition
    return None


def _first_partition(disk_session):
    """the first partition of the lowest unit that has one, or ``None``"""
    for unit in disk_session.get_units():
        backend = disk_session.get_backend(unit)
        for partition in getattr(backend, "partitions", ()):
            return unit, partition
    return None


def resolve_blkdev(disk_session, config, name=None):
    """build a :class:`BlkDevSpec` from a ``NativeConfig``

    ``config.device`` names the DOS device node of a partition, ``config.part``
    the RDB partition directly; ``name`` is the mount name used when neither is
    set. A partition that can be resolved in the disk session supplies the unit,
    the geometry and its DOS device name; otherwise a synthetic geometry is
    used.
    """
    unit = config.unit
    geometry = None
    partition_name = None
    driver_data = None
    driver_globvec = None

    if disk_session is not None:
        selector = config.part
        if selector is None:
            selector = config.device
        if selector is None:
            selector = name
        found = _find_partition(disk_session, selector)
        if found is None:
            # no match (or no selector at all): fall back to the first
            # partition so a single-disk setup still mounts
            found = _first_partition(disk_session)
        if found is not None:
            found_unit, partition = found
            geometry = partition.dos_env
            partition_name = partition.name.rstrip(":")
            # the RDB driver is an optional handler source (step 24d)
            driver_data = getattr(partition, "driver_data", None)
            driver_globvec = getattr(partition, "driver_globvec", None)
            if unit is None:
                unit = found_unit

    if geometry is None:
        log_handler.debug("native handler: no disk partition, using synthetic geometry")
        geometry = BlkDevGeometry()
    if unit is None:
        unit = 0
    return BlkDevSpec(
        DEFAULT_DEVICE,
        unit,
        geometry,
        partition_name,
        driver_data=driver_data,
        driver_globvec=driver_globvec,
    )
