from amitools.vamos.lib.lexec.modfunc import ModuleMixin
from lib_exec_helper import ExecHost, make_exec_lib


class Host(ExecHost, ModuleMixin):
    pass


def exec_init_code_test():
    mem, alloc, el = make_exec_lib()
    host = Host(mem, alloc, el)
    # no ROM modules: always returns NULL
    assert host.InitCode(host.ctx, 0, 0) == 0
    assert host.InitCode(host.ctx, 1, 47) == 0
