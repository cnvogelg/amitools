import pytest

from amitools.vamos.lib.graphics import (
    BitMapStruct,
    LayerInfoStruct,
    LayerStruct,
    RastPortStruct,
)
from amitools.vamos.lib.intuition import (
    IntuiMessageStruct,
    ScreenStruct,
    TextFontStruct,
    WindowStruct,
)
from amitools.vamos.machine import (
    Code,
    Machine,
    Runtime,
    REG_A0,
    REG_D1,
    REG_D2,
    REG_D3,
)
from amitools.vamos.machine.mock import MockMemory
from amitools.vamos.mem import MemoryAlloc


# Sizes and offsets from the public NDK headers, independently checked by
# compiling sizeof/offsetof expressions with m68k-amigaos-gcc.
@pytest.mark.parametrize(
    "layout,size",
    [
        (RastPortStruct, 100),
        (ScreenStruct, 346),
        (BitMapStruct, 40),
        (WindowStruct, 136),
        (LayerStruct, 160),
        (LayerInfoStruct, 102),
        (TextFontStruct, 52),
        (IntuiMessageStruct, 52),
    ],
)
def libstructs_graphics_public_size_test(layout, size):
    assert layout.get_size() == size


@pytest.mark.parametrize(
    "layout,field,offset",
    [
        (RastPortStruct, "Font", 52),
        (RastPortStruct, "RP_User", 66),
        (RastPortStruct, "longreserved", 70),
        (RastPortStruct, "wordreserved", 78),
        (RastPortStruct, "reserved", 92),
        (ScreenStruct, "RastPort", 84),
        (ScreenStruct, "BitMap", 184),
        (ScreenStruct, "LayerInfo", 224),
        (ScreenStruct, "FirstGadget", 326),
        (ScreenStruct, "UserData", 342),
    ],
)
def libstructs_graphics_public_offset_test(layout, field, offset):
    value = layout(MockMemory(), 0x100)
    assert value.get(field).get_addr() == 0x100 + offset


def libstructs_graphics_full_rastport_copy_test():
    mem = MockMemory()
    alloc = MemoryAlloc(mem)
    rp = RastPortStruct.alloc(alloc)
    neighbor = alloc.alloc_memory(32)
    marker = b"x" * 32
    mem.w_block(neighbor.addr, marker)
    try:
        # A guest compiled against the NDK can copy the entire public
        # structure, including the reserved tail, into its allocation.
        mem.w_block(rp.get_addr(), bytes(100))
        assert mem.r_block(neighbor.addr, 32) == marker
    finally:
        alloc.free_memory(neighbor)
        rp.free()
    assert alloc.is_all_free()


def libstructs_graphics_native_screen_offsets_test():
    machine = Machine()
    alloc = MemoryAlloc.for_machine(machine)
    mem = machine.get_mem()
    screen = ScreenStruct.alloc(alloc)
    code = alloc.alloc_memory(16)
    try:
        screen.BitMap.BytesPerRow.val = 8
        screen.BitMap.Rows.val = 32
        screen.LayerInfo.top_layer.val = 0x12345678
        screen.FirstGadget.val = 0xCAFEBABE
        # Read Screen.BitMap, LayerInfo.top_layer and FirstGadget using
        # SDK offsets: move.l 184(a0),d1; move.l 224(a0),d2;
        # move.l 326(a0),d3; rts.
        mem.w_block(code.addr, bytes.fromhex("222800b8242800e0262801464e75"))
        result = Runtime(machine).start(
            Code(
                code.addr,
                machine.get_scratch_top(),
                set_regs={REG_A0: screen.get_addr()},
                get_regs=[REG_D1, REG_D2, REG_D3],
            )
        )
        assert result.exit
        assert result.regs == {
            REG_D1: 0x00080020,
            REG_D2: 0x12345678,
            REG_D3: 0xCAFEBABE,
        }
    finally:
        alloc.free_memory(code)
        screen.free()
        assert alloc.is_all_free()
        machine.cleanup()
