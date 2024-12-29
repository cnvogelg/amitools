from amitools.vamos.astructs import (
    AmigaStructDef,
    AmigaStruct,
    ULONG,
)
from .exec_ import IORequestStruct


# TimeVal
@AmigaStructDef
class TimeValStruct(AmigaStruct):
    _format = [(ULONG, "tv_secs"), (ULONG, "tv_micro")]


# TimeRequest
@AmigaStructDef
class TimeRequestStruct(AmigaStruct):
    _format = [
        (IORequestStruct, "tr_node"),
        (TimeValStruct, "tr_time"),
    ]
