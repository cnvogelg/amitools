"""Direct SCSI command layout from devices/scsidisk.h."""

from amitools.vamos.astructs import AmigaStruct, AmigaStructDef
from amitools.vamos.astructs.scalar import UBYTE, ULONG, UWORD


@AmigaStructDef
class SCSICmdStruct(AmigaStruct):
    _format = [
        (ULONG, "scsi_Data"),
        (ULONG, "scsi_Length"),
        (ULONG, "scsi_Actual"),
        (ULONG, "scsi_Command"),
        (UWORD, "scsi_CmdLength"),
        (UWORD, "scsi_CmdActual"),
        (UBYTE, "scsi_Flags"),
        (UBYTE, "scsi_Status"),
        (ULONG, "scsi_SenseData"),
        (UWORD, "scsi_SenseLength"),
        (UWORD, "scsi_SenseActual"),
    ]
