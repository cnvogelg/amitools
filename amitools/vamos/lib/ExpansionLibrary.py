"""
Minimal expansion.library for vamos.

Programs sometimes probe the AutoConfig expansion bus via FindConfigDev() to
check that a particular board is present before they run. vamos has no real
AutoConfig chain, so this library simulates a single demo board, letting such
checks succeed under the emulator.

Only the handful of calls a typical probe makes are implemented; the rest are
no-op stubs so an unexpected call does not crash the emulator. The demo board's
manufacturer/product ids can be adjusted below to match what a given program
looks for.
"""

from amitools.vamos.libcore import LibImpl

# AutoConfig ids reported by the simulated demo board.
DEMO_MANUFACTURER = 0x89E
DEMO_PRODUCT = 0x19

# struct ConfigDev is ~0x44 bytes. We only need enough to look like a board.
CONFIGDEV_SIZE = 0x44
# offsets inside struct ConfigDev
CD_ROM = 0x10              # struct ExpansionRom cd_Rom
ER_TYPE = CD_ROM + 0x00    # er_Type (UBYTE)
ER_PRODUCT = CD_ROM + 0x01  # er_Product (UBYTE)
ER_MANUFACTURER = CD_ROM + 0x04  # er_Manufacturer (UWORD)
CD_BOARDADDR = 0x20        # cd_BoardAddr (APTR)
CD_BOARDSIZE = 0x24        # cd_BoardSize (ULONG)

# er_Type bits: ERTF_ZORROII (0xC0 = board present, Zorro II)
ERT_ZORROII = 0xC0


class ExpansionLibrary(LibImpl):
    def __init__(self):
        self._configdev_addr = 0

    def _ensure_configdev(self, ctx):
        """Allocate + populate the demo ConfigDev on first use."""
        if self._configdev_addr:
            return self._configdev_addr
        mem_obj = ctx.alloc.alloc_memory(CONFIGDEV_SIZE, label="DemoConfigDev")
        addr = mem_obj.addr
        ctx.mem.w_block(addr, b"\x00" * CONFIGDEV_SIZE)
        ctx.mem.w8(addr + ER_TYPE, ERT_ZORROII)
        ctx.mem.w8(addr + ER_PRODUCT, DEMO_PRODUCT)
        ctx.mem.w16(addr + ER_MANUFACTURER, DEMO_MANUFACTURER)
        # plausible Zorro II board window so anything that reads it sees memory
        ctx.mem.w32(addr + CD_BOARDADDR, 0x00DA0000)
        ctx.mem.w32(addr + CD_BOARDSIZE, 0x00010000)
        self._configdev_addr = addr
        return addr

    def FindConfigDev(self, ctx, old_configdev, manufacturer, product):
        """Return the simulated demo board when its ids are requested.

        Args match the .fd: oldConfigDev in a0, manufacturer in d0, product in
        d1. -1 (0xFFFFFFFF) is the AutoConfig wildcard meaning "any".
        """
        man = manufacturer & 0xFFFFFFFF
        prod = product & 0xFFFFFFFF
        if man not in (0xFFFFFFFF, DEMO_MANUFACTURER):
            return 0
        if prod not in (0xFFFFFFFF, DEMO_PRODUCT):
            return 0
        # We simulate exactly one board: a non-null oldConfigDev means the
        # caller is iterating past it, so there is nothing more to find.
        if (old_configdev & 0xFFFFFFFF) not in (0, 0xFFFFFFFF):
            return 0
        return self._ensure_configdev(ctx)

    # ---- calls a probe commonly makes that must succeed harmlessly ----

    def GetCurrentBinding(self, ctx, current_binding, binding_size):
        return 0

    def ObtainConfigBinding(self, ctx):
        return 0

    def ReleaseConfigBinding(self, ctx):
        return 0

    def ReadExpansionByte(self, ctx, board, offset):
        return 0

    # ---- remaining LVOs: no-op stubs ----

    def AddConfigDev(self, ctx, config_dev):
        return 0

    def AllocConfigDev(self, ctx):
        return 0

    def FreeConfigDev(self, ctx, config_dev):
        return 0

    def RemConfigDev(self, ctx, config_dev):
        return 0
