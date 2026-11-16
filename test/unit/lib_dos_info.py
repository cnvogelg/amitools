from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.handler import HandlerError, HandlerInfoData
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import InfoDataStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2


def _make_lib(info):
    ctx = SimpleNamespace(mem=MockMemory(), cpu=MockCPU())
    ctx.cpu.w_reg(REG_D1, 64)
    ctx.cpu.w_reg(REG_D2, 512)
    handler = SimpleNamespace(info=info)
    lock = SimpleNamespace(
        handler=handler,
        handler_lock=object(),
        find_volume_node=lambda dl: 1024,
    )
    lib = DosLibrary()
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda addr: lock)
    lib.dos_list = None
    lib.setioerr = Mock()
    return lib, ctx


@pytest.mark.parametrize("blocks", [1000, 1 << 33])
def dos_info_host_capacity_test(blocks):
    def info(lock):
        return HandlerInfoData(
            num_blocks=blocks,
            num_blocks_used=blocks // 2,
            bytes_per_block=4096,
        )

    lib, ctx = _make_lib(info)
    assert lib.Info(ctx) != 0
    data = InfoDataStruct(ctx.mem, 512)
    assert data.id_NumBlocks.val <= 0x7FFFFFFF
    assert data.id_NumBlocks.val * data.id_BytesPerBlock.val == blocks * 4096
    assert data.id_NumBlocksUsed.val * data.id_BytesPerBlock.val == blocks * 2048
    assert data.id_VolumeNode.aptr == 1024
    lib.setioerr.assert_called_once_with(ctx, 0)


def dos_info_missing_host_path_test():
    def info(lock):
        raise HandlerError(205)

    lib, ctx = _make_lib(info)
    assert lib.Info(ctx) == 0
    assert lib.setioerr.call_args.args[1] != 0
