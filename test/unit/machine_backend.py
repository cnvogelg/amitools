from amitools.vamos.machine import (
    Backend,
    Machine68kBackend,
    RMachine68kBackend,
)


def machine_backend_default_test():
    back = Backend.get_default()
    assert back is not None
    mach = back.create_machine()
    assert mach is not None


def machine_backend_machine68k_test():
    back = Machine68kBackend()
    mach = back.create_machine()
    assert type(mach).__name__ == "Machine"


def machine_backend_machine68k_from_cfg_test():
    cfg = {"name": "machine68k"}
    back = Backend.from_cfg(cfg)
    mach = back.create_machine()
    assert type(mach).__name__ == "Machine"


def machine_backend_rmachine68k_test(rmachine68k_server):
    port = rmachine68k_server
    back = RMachine68kBackend(host="localhost", port=port)
    mach = back.create_machine()
    assert type(mach).__name__ == "RMachine68k"


def machine_backend_rmachine68k_from_cfg_test(rmachine68k_server):
    port = rmachine68k_server
    cfg = {"name": "rmachine68k", "host": "localhost", "port": str(port)}
    back = Backend.from_cfg(cfg)
    mach = back.create_machine()
    assert type(mach).__name__ == "RMachine68k"
