import io
from contextlib import redirect_stderr


def pytask_exec_rawio_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()

        assert exec_proxy.RawMayGetChar() == 0xFFFFFFFF

        exec_proxy.RawPutChar(ord("A"))
        exec_proxy.RawPutChar(10)
        exec_proxy.RawPutChar(0)
        exec_proxy.RawPutChar(ord("B"))
        exec_proxy.RawPutChar(10)
        return 0

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        exit_codes = vamos_task.run([task])

    assert exit_codes == [0]
    assert stderr.getvalue() == "A\r\nB\r\n"
