from amitools.vamos.astructs import (
    AmigaStructDef,
    AmigaStruct,
    ULONG,
)
from .exec_ import IORequestBaseStruct


# TimeVal
@AmigaStructDef
class TimeValStruct(AmigaStruct):
    _format = [(ULONG, "tv_secs"), (ULONG, "tv_micro")]


# TimeRequest
@AmigaStructDef
class TimeRequestStruct(AmigaStruct):
    _format = [
        (IORequestBaseStruct, "tr_node"),
        (TimeValStruct, "tr_time"),
    ]
