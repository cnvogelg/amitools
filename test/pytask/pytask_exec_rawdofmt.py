import struct


BUFFERED_PUT_CODE = (
    0x2F0B,
    0x2F02,
    0x7201,
    0xB2AB,
    0x0004,
    0x6C10,
    0x2213,
    0x2401,
    0x5282,
    0x2682,
    0x2041,
    0x1080,
    0x53AB,
    0x0004,
    0x241F,
    0x265F,
    0x4E75,
)


def pytask_exec_rawdofmt_buffered_putproc_test(vamos_task):
    def task(ctx, task):
        exec_proxy = ctx.proxies.get_exec_lib_proxy()
        alloc = ctx.alloc
        mem = ctx.mem

        fmt = alloc.alloc_memory(16, "fmt")
        code = alloc.alloc_memory(len(BUFFERED_PUT_CODE) * 2, "putproc")
        buf = alloc.alloc_memory(16, "buf")
        put_data = alloc.alloc_memory(8, "putdata")
        try:
            mem.w_cstr(fmt.addr, "Hello")
            mem.w_block(
                code.addr,
                b"".join(struct.pack(">H", x) for x in BUFFERED_PUT_CODE),
            )
            mem.clear_block(buf.addr, 16, 0)
            mem.w32(put_data.addr, buf.addr)
            mem.w32(put_data.addr + 4, 16)

            assert exec_proxy.RawDoFmt(fmt.addr, 0, code.addr, put_data.addr) == 0
            assert mem.r_cstr(buf.addr) == "Hello"
            assert mem.r32(put_data.addr) == buf.addr + 6
            assert mem.r32(put_data.addr + 4) == 10
        finally:
            alloc.free_memory(put_data)
            alloc.free_memory(buf)
            alloc.free_memory(code)
            alloc.free_memory(fmt)
        return 0

    exit_codes = vamos_task.run([task])
    assert exit_codes == [0]
