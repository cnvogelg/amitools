"""Open and create volumes of all supported file systems: OFS/FFS and PFS3"""

from . import DosType
from .ADFSVolume import ADFSVolume
from .pfs3 import is_pfs3_blkdev
from .pfs3.PFS3Volume import PFS3Volume


def open_volume(blkdev):
    """open the volume of a block device: PFS3 if its boot block says so,
    else OFS/FFS"""
    if is_pfs3_blkdev(blkdev):
        vol = PFS3Volume(blkdev)
    else:
        vol = ADFSVolume(blkdev)
    vol.open()
    return vol


def create_volume(
    blkdev, name, meta_info=None, dos_type=None, boot_code=None, **pfs3_options
):
    """format a block device: with PFS3 if dos_type is one of its types,
    else with OFS/FFS. pfs3_options (fnsize, largefile, numreserved) are
    passed on to PFS3Volume.create()"""
    if dos_type is not None and DosType.is_pfs(dos_type):
        vol = PFS3Volume(blkdev)
        vol.create(
            name,
            meta_info=meta_info,
            dos_type=dos_type,
            boot_code=boot_code,
            **pfs3_options,
        )
    else:
        vol = ADFSVolume(blkdev)
        vol.create(name, meta_info=meta_info, dos_type=dos_type, boot_code=boot_code)
    return vol
