"""Layout checks for the Exec IO request structs and timer.device's request.

A ``struct timerequest`` embeds the plain ``struct IORequest`` (0x20 bytes),
not the larger ``struct IOStdReq`` (0x30). Getting this wrong moves
``tr_time`` from offset 0x20 to 0x30 and makes ``timer.device`` write past the
end of the caller's request; SFS builds a ``struct timerequest`` on its stack
and was corrupted by exactly that (its saved A5 was overwritten by
``TR_GETSYSTIME``'s ``tv_micro``).
"""

from amitools.vamos.libstructs import (
    IORequestBaseStruct,
    IORequestStruct,
    TimeRequestStruct,
    TimeValStruct,
)


def libstructs_timer_iorequest_layout_test():
    # NDK exec/io.h: struct IORequest is 0x20 bytes
    assert IORequestBaseStruct.get_byte_size() == 0x20
    # NDK exec/io.h: struct IOStdReq adds io_Actual/io_Length/io_Data/io_Offset
    assert IORequestStruct.get_byte_size() == 0x30


def libstructs_timer_timerequest_layout_test():
    # NDK devices/timer.h: struct timerequest = struct IORequest + struct TimeVal
    assert TimeValStruct.get_byte_size() == 0x8
    assert TimeRequestStruct.get_byte_size() == 0x28
    assert TimeRequestStruct.sdef.find_field_def_by_name("tr_node").offset == 0x0
    assert TimeRequestStruct.sdef.find_field_def_by_name("tr_time").offset == 0x20
