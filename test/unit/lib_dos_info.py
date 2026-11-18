from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from amitools.vamos.handler import HandlerError, HandlerFileInfo, HandlerInfoData
from amitools.vamos.lib.DosLibrary import DosLibrary
from amitools.vamos.lib.dos.Error import DOSFALSE, DOSTRUE
from amitools.vamos.lib.dos.Lock import Lock
from amitools.vamos.libstructs import FileInfoBlockStruct, InfoDataStruct
from amitools.vamos.machine.mock import MockCPU, MockMemory
from amitools.vamos.machine.regs import REG_D1, REG_D2

# distinguishes "no handler lock" (None) from "use the default"
_UNSET = object()


def _make_lib(info, handler_lock=_UNSET, volume_name="work:", handler_mgr=None):
    ctx = SimpleNamespace(mem=MockMemory(), cpu=MockCPU())
    ctx.cpu.w_reg(REG_D1, 64)
    ctx.cpu.w_reg(REG_D2, 512)
    handler = SimpleNamespace(info=info)
    lock = SimpleNamespace(
        handler=handler,
        handler_lock=object() if handler_lock is _UNSET else handler_lock,
        find_volume_node=lambda dl: 1024,
    )
    lib = DosLibrary()
    lib.lock_mgr = SimpleNamespace(
        get_by_b_addr=lambda addr: lock,
        volume_name_of_lock=lambda lock: volume_name,
    )
    lib.dos_list = None
    lib.handler_mgr = handler_mgr
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


def dos_info_lockless_volume_fallback_test():
    # a lock without a handler lock (a lock-less volume query) resolves the
    # volume through the handler manager
    handler_mgr = Mock()
    handler_mgr.disk_info.return_value = HandlerInfoData(
        num_blocks=100,
        num_blocks_used=50,
        bytes_per_block=512,
    )
    lib, ctx = _make_lib(
        info=lambda lock: None,
        handler_lock=None,
        volume_name="work:",
        handler_mgr=handler_mgr,
    )

    assert lib.Info(ctx) != 0
    handler_mgr.disk_info.assert_called_once_with("work:")
    data = InfoDataStruct(ctx.mem, 512)
    assert data.id_NumBlocks.val == 100
    assert data.id_NumBlocksUsed.val == 50
    assert data.id_BytesPerBlock.val == 512
    lib.setioerr.assert_called_once_with(ctx, 0)


def dos_info_lockless_volume_unknown_test():
    # the manager raises for an unknown volume; Info() maps its code to IoErr
    def disk_info(volume_name):
        raise HandlerError(205)

    handler_mgr = SimpleNamespace(disk_info=disk_info)
    lib, ctx = _make_lib(
        info=lambda lock: None, handler_lock=None, handler_mgr=handler_mgr
    )

    assert lib.Info(ctx) == 0
    assert lib.setioerr.call_args.args[1] == 205


# ----- ExamineFH (ACTION_EXAMINE_FH) -----


def _make_fh_lib(fh, lock=None):
    ctx = SimpleNamespace(
        mem=MockMemory(),
        cpu=MockCPU(),
        process=SimpleNamespace(get_current_dir=lambda: 0),
    )
    ctx.cpu.w_reg(REG_D1, 20)
    ctx.cpu.w_reg(REG_D2, 512)
    lib = DosLibrary()
    lib.file_mgr = SimpleNamespace(get_by_b_addr=lambda b, w=None: fh)
    lib.lock_mgr = SimpleNamespace(
        get_by_b_addr=lambda b: None,
        create_lock=lambda cwd, ami_path, exclusive: lock,
        release_lock=lambda _l: None,
    )
    lib.setioerr = Mock()
    return lib, ctx


def _file_info():
    return HandlerFileInfo(
        name="f",
        entry_type=HandlerFileInfo.FILE,
        size=42,
        blocks=3,
        key=7,
    )


def dos_info_examine_fh_handler_test():
    # a handler-backed handle examines the object via ACTION_EXAMINE_FH
    handler = SimpleNamespace(examine_fh=lambda hf: _file_info())
    handler_file = object()
    fh = SimpleNamespace(handler=handler, handler_file=handler_file, name="f")
    lib, ctx = _make_fh_lib(fh)

    assert lib.ExamineFH(ctx) == DOSTRUE
    fib = FileInfoBlockStruct(ctx.mem, 512)
    assert ctx.mem.r_cstr(fib.fib_FileName.addr) == "f"
    assert fib.fib_Size.val == 42
    assert fib.fib_NumBlocks.val == 3
    assert fib.fib_DirEntryType.val == HandlerFileInfo.FILE
    lib.setioerr.assert_called_once_with(ctx, 0)


def dos_info_examine_fh_handler_error_test():
    def examine_fh(hf):
        raise HandlerError(205)

    fh = SimpleNamespace(
        handler=SimpleNamespace(examine_fh=examine_fh),
        handler_file=object(),
        name="f",
    )
    lib, ctx = _make_fh_lib(fh)

    assert lib.ExamineFH(ctx) == DOSFALSE
    assert lib.setioerr.call_args.args[1] == 205


def dos_info_examine_fh_fallback_test():
    # a handler-less handle examines via a temporary lock
    handler = SimpleNamespace(examine_object=lambda hl: _file_info())
    lock = Lock("f", "work:f", handler=handler, handler_lock=object())
    fh = SimpleNamespace(handler=None, handler_file=None, ami_path="work:f", name="f")
    lib, ctx = _make_fh_lib(fh, lock=lock)

    assert lib.ExamineFH(ctx) == DOSTRUE
    fib = FileInfoBlockStruct(ctx.mem, 512)
    assert ctx.mem.r_cstr(fib.fib_FileName.addr) == "f"
    assert fib.fib_Size.val == 42
    lib.setioerr.assert_called_once_with(ctx, 0)
