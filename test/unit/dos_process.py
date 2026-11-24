"""DOS process base (ProcessBase): the ``self.proc`` dedup.

Step 2 of the shell refactor folded the old ``self.this_task`` ProcessStruct
view into ``self.proc`` (the ``libtypes.Process`` allocated by ``DosProcess``)
and dropped the duplicated dir/var/cli accessors.  These tests pin that down
without needing a full vamos context.
"""

from types import SimpleNamespace

from amitools.vamos.lib.dos.Process import ProcessBase
from amitools.vamos.task import DosProcess


class _Proc:
    def __init__(self):
        self.pr_CIS = SimpleNamespace(aptr=0)
        self.pr_COS = SimpleNamespace(aptr=0)
        self.pr_Arguments = SimpleNamespace(aptr=0)


class _FileMgr:
    def __init__(self):
        self.files = {0x10: "in", 0x20: "out"}

    def get_by_b_addr(self, b_addr):
        return self.files.get(b_addr)


def _make_process():
    proc = _Proc()
    file_mgr = _FileMgr()
    ctx = SimpleNamespace(dos_lib=SimpleNamespace(file_mgr=file_mgr))
    p = ProcessBase.__new__(ProcessBase)
    p.ctx = ctx
    p.proc = proc
    return p, proc, file_mgr


def dos_process_this_task_is_proc_test():
    # this_task is only an alias for the already allocated self.proc struct
    p, proc, _ = _make_process()
    assert p.this_task is proc


def dos_process_stream_accessors_test():
    p, proc, file_mgr = _make_process()
    in_fh = SimpleNamespace(b_addr=0x10)
    out_fh = SimpleNamespace(b_addr=0x20)

    p.set_input(in_fh)
    assert proc.pr_CIS.aptr == 0x10 << 2
    p.set_output(out_fh)
    assert proc.pr_COS.aptr == 0x20 << 2

    assert p.get_input() == "in"
    assert p.get_output() == "out"

    # BNULL clears the field instead of writing a handle
    p.set_input(None)
    p.set_output(None)
    assert proc.pr_CIS.aptr == 0
    assert proc.pr_COS.aptr == 0


def dos_process_arg_str_accessors_test():
    p, proc, _ = _make_process()
    p.set_arg_str_ptr(0x1234)
    assert proc.pr_Arguments.aptr == 0x1234
    assert p.get_arg_str_ptr() == 0x1234


def dos_process_inherited_accessors_test():
    # the dir/var/cli accessors are no longer duplicated in ProcessBase
    for name in (
        "get_current_dir",
        "set_current_dir",
        "get_home_dir",
        "set_home_dir",
        "get_local_vars",
        "get_cli_struct",
    ):
        assert getattr(ProcessBase, name) is getattr(DosProcess, name)
