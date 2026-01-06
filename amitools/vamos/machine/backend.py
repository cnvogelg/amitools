from amitools.vamos.log import log_machine


class Backend:
    def create_machine(self, cpu_name, ram_size_kib):
        raise NotImplementedError("implement in derived class")

    @classmethod
    def get_default(cls):
        return Machine68kBackend()

    @classmethod
    def from_cfg(cls, cfg):
        if cfg is None:
            return Machine68kBackend()
        name = cfg.get("name", "machine68k")
        if name in ("m68k", "machine68k"):
            return Machine68kBackend()
        elif name in ("rm68k", "rmachine68k"):
            host = cfg.get("host", "localhost")
            port = int(cfg.get("port", "18861"))
            return RMachine68kBackend(host, port)
        else:
            log_machine.error("invalid backend name '%s'!", name)
            return None


class Machine68kBackend:
    def create_machine(self, cpu_name="68000", ram_size_kib=1024):
        try:
            import machine68k

            cpu_type = machine68k.cpu_type_from_str(cpu_name)
            log_machine.info(
                "create machine68k with cpu_type=%s ram_size=%d", cpu_type, ram_size_kib
            )
            return machine68k.Machine(cpu_type, ram_size_kib)
        except ImportError:
            log_machine.info(
                "can't create machine68k. please install package 'machine68k' first!"
            )
            return None


class RMachine68kBackend:
    def __init__(self, host="localhost", port=18861):
        self.host = host
        self.port = port

    def create_machine(self, cpu_name="68000", ram_size_kib=1024):
        try:
            import rmachine68k

            log_machine.info(
                "create rmachine68k client to host=%s port=%d", self.host, self.port
            )
            try:
                client = rmachine68k.create_client(self.host, self.port)
            except OSError as e:
                log_machine.error(
                    "rmachine68k: host=%s port=%d: %s",
                    self.host,
                    self.port,
                    e,
                )
                return None
            log_machine.info(
                "create rmachine68k with cpu_type=%s ram_size=%d",
                cpu_name,
                ram_size_kib,
            )
            return rmachine68k.create_machine(client, cpu_name, ram_size_kib)
        except ImportError:
            log_machine.info(
                "can't create rmachine68k. please install package 'rmachine68k' first!"
            )
            return None
