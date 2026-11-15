from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.libstructs import InfoDataStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2


@pytest.mark.parametrize("portable", [False, True])
@pytest.mark.parametrize("blocks", [1000, 1 << 33])
def dos_info_host_capacity_test(monkeypatch, portable, blocks):
    import os
    import shutil

    ctx = SimpleNamespace(mem=MockMemory(), cpu=MockCPU())
    ctx.cpu.w_reg(REG_D1, 64)
    ctx.cpu.w_reg(REG_D2, 512)
    lock = SimpleNamespace(sys_path="/host", find_volume_node=lambda dl: 1024)
    lib = DosLibrary()
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda addr: lock)
    lib.dos_list = None
    lib.setioerr = Mock()
    if portable:
        monkeypatch.delattr(os, "statvfs", raising=False)
        monkeypatch.setattr(
            shutil,
            "disk_usage",
            lambda path: SimpleNamespace(total=blocks * 4096, used=blocks * 2048),
        )
    else:
        monkeypatch.setattr(
            os,
            "statvfs",
            lambda path: SimpleNamespace(
                f_flag=0,
                f_frsize=4096,
                f_bsize=4096,
                f_blocks=blocks,
                f_bfree=blocks // 2,
            ),
            raising=False,
        )
    assert lib.Info(ctx) != 0
    info = InfoDataStruct(ctx.mem, 512)
    assert info.id_NumBlocks.val <= 0x7FFFFFFF
    assert info.id_NumBlocks.val * info.id_BytesPerBlock.val == blocks * 4096
    assert info.id_NumBlocksUsed.val * info.id_BytesPerBlock.val == blocks * 2048
    assert info.id_VolumeNode.aptr == 1024
    lib.setioerr.assert_called_once_with(ctx, 0)


def dos_info_missing_host_path_test(monkeypatch):
    import os

    ctx = SimpleNamespace(mem=MockMemory(), cpu=MockCPU())
    ctx.cpu.w_reg(REG_D2, 512)
    lock = SimpleNamespace(sys_path="/missing", find_volume_node=lambda dl: 1024)
    lib = DosLibrary()
    lib.lock_mgr = SimpleNamespace(get_by_b_addr=lambda addr: lock)
    lib.dos_list = None
    lib.setioerr = Mock()
    monkeypatch.setattr(os, "statvfs", Mock(side_effect=OSError), raising=False)
    assert lib.Info(ctx) == 0
    assert lib.setioerr.call_args.args[1] != 0
