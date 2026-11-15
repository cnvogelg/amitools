"""PTY input barrier for the native WaitForChar regression."""


def wait_for_input(ctx):
    from amitools.fd import read_lib_fd
    from amitools.vamos.libcore import LibProxyGen

    generator = LibProxyGen()
    executive_type = generator.gen_proxy_for_libcall(
        "exec", read_lib_fd("exec.library")
    )
    dos_type = generator.gen_proxy_for_libcall("dos", read_lib_fd("dos.library"))
    executive = executive_type(ctx, ctx.mem.r32(4))
    name = ctx.alloc.alloc_cstr("dos.library")
    library = executive.OpenLibrary(name.addr, 0)
    ctx.alloc.free_memory(name)
    assert library
    dos = dos_type(ctx, library)
    marker = ctx.alloc.alloc_memory(1)
    handle = dos.Input()
    try:
        assert dos.SetMode(handle, 1) == 0xFFFFFFFF
        # The parent can write only after raw mode is active. Consume a
        # marker before starting the timeout, leaving its following byte
        # in the terminal queue even if the parent was descheduled.
        print("timeout=100000", flush=True)
        assert dos.Read(handle, marker.addr, 1) == 1
        result = dos.WaitForChar(handle, 100000)
        result = -1 if result == 0xFFFFFFFF else result
    finally:
        dos.SetMode(handle, 0)
        ctx.alloc.free_memory(marker)
        executive.CloseLibrary(library)
    print("result=%d" % result, flush=True)
    return 0 if result == -1 else 1
