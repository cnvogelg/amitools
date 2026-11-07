from amitools.vamos.libstructs import ExAllControlStruct, ExAllDataStruct
from amitools.vamos.lib.dos.Error import DOSTRUE, ERROR_NO_MORE_ENTRIES


def pytask_dos_exall_end_test(vamos_task, tmp_path):
    directory = tmp_path / "scan"
    directory.mkdir()
    for name in ("alpha", "bravo", "charlie"):
        (directory / name).write_bytes(name.encode())

    def proc(ctx, task):
        dos = ctx.proxies.get_dos_lib_proxy()
        buffer = ctx.alloc.alloc_memory(24)
        lock_obj = ctx.dos_lib.lock_mgr.create_lock(
            None, "root:" + str(directory)[1:], False
        )
        lock = lock_obj.b_addr
        assert lock != 0
        control_ptr = dos.AllocDosObject(1, 0)
        assert control_ptr != 0
        control = ExAllControlStruct(ctx.mem, control_ptr)
        try:
            assert dos.ExAll(lock, buffer.addr, 24, 3, control_ptr) == DOSTRUE
            assert control.eac_Entries.val == 1
            assert control_ptr in ctx.dos_lib.exall_scans
            dos.ExAllEnd(lock, buffer.addr, 24, 3, control_ptr)
            assert control.eac_Entries.val == 0
            assert control.eac_LastKey.val == 0
            assert control_ptr not in ctx.dos_lib.exall_scans
            # The same control can start a complete new scan after abort.
            found = []
            while True:
                more = dos.ExAll(lock, buffer.addr, 24, 3, control_ptr)
                if control.eac_Entries.val:
                    entry = ExAllDataStruct(ctx.mem, buffer.addr)
                    found.append(ctx.mem.r_cstr(entry.ed_Name.aptr))
                if not more:
                    assert dos.IoErr() == ERROR_NO_MORE_ENTRIES
                    break
            assert sorted(found) == ["alpha", "bravo", "charlie"]
        finally:
            dos.FreeDosObject(1, control_ptr)
            dos.UnLock(lock)
            ctx.alloc.free_memory(buffer)
        return 0

    assert vamos_task.run(
        [proc],
        process=True,
        args=["--vols-base-dir", str(tmp_path / "volumes")],
    ) == [0]
