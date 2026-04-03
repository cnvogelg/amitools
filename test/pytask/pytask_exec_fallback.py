import os
import tempfile
from amitools.vamos.lib.lexec.signalfunc import SignalFunc
from amitools.vamos.libtypes import Message, MsgPort
from amitools.vamos.main import main
from pathlib import Path


TEST_VAMOSRC = str(Path(__file__).resolve().parents[1] / "test.vamosrc")


def _reset_fallback_signals():
    SignalFunc._fallback_signals = 0
    SignalFunc._fallback_sig_alloc = 0x0000FFFF


def _run_fallback(check):
    class FallbackMode:
        def run(self, mode_ctx):
            ctx = mode_ctx.exec_ctx
            assert ctx.task is None
            check(ctx)
            return [0]

    _reset_fallback_signals()
    try:
        old_home = os.environ.get("HOME")
        with tempfile.TemporaryDirectory() as tmp_home:
            os.environ["HOME"] = tmp_home
            exit_codes = main(args=["-c", TEST_VAMOSRC], mode=FallbackMode())
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
        _reset_fallback_signals()
    assert exit_codes == 0


def pytask_exec_signal_fallback_test():
    def check(ctx):
        exec_lib = ctx.proxies.get_exec_lib_proxy()

        sig = exec_lib.AllocSignal(-1)
        assert sig == 16

        mask = 1 << sig
        assert exec_lib.SetSignal(mask, mask) == 0
        assert exec_lib.SetSignal(0, 0) == mask
        assert exec_lib.SetSignal(0, mask) == mask
        assert exec_lib.SetSignal(0, 0) == 0

        exec_lib.FreeSignal(sig)

        assert exec_lib.AllocSignal(sig) == sig
        exec_lib.FreeSignal(sig)

    _run_fallback(check)


def pytask_exec_msg_fallback_test():
    def check(ctx):
        exec_lib = ctx.proxies.get_exec_lib_proxy()
        port = exec_lib.CreateMsgPort()
        assert type(port) is MsgPort
        assert port.sig_bit.val == 0
        assert exec_lib.FindTask(None) == port.sig_task.ref

        msg = Message.alloc(ctx.alloc)
        assert msg

        assert exec_lib.GetMsg(port) is None

        exec_lib.PutMsg(port, msg)
        assert exec_lib.SetSignal(0, 0) & 1 == 1

        msg2 = exec_lib.GetMsg(port)
        assert msg2 == msg
        assert exec_lib.GetMsg(port) is None

        exec_lib.SetSignal(0, 1)
        msg.reply_port.ref = port
        exec_lib.ReplyMsg(msg)
        assert exec_lib.SetSignal(0, 0) & 1 == 1
        assert exec_lib.GetMsg(port) == msg

        exec_lib.DeleteMsgPort(port)
        msg.free()

    _run_fallback(check)
