from amitools.vamos.machine import CPUHWExceptionHandler


def machine_hwexc_setup_test():
    # no dict, no handler
    handler = CPUHWExceptionHandler.from_cfg(None)
    assert handler is None
    # empty dict, no handler
    handler = CPUHWExceptionHandler.from_cfg({})
    assert handler is None
    # non empty dict
    handler = CPUHWExceptionHandler.from_cfg({"bus": "ignore"})
    assert type(handler) is CPUHWExceptionHandler


class FakeHwExc:
    def __init__(self, exc_num):
        self.exc_num = exc_num


def machine_hwexc_handler_test():
    # ignore
    handler = CPUHWExceptionHandler.from_cfg({"bus": "ignore"})
    exc = FakeHwExc(2)
    assert handler.handle_error(exc) is True
    # trace
    handler = CPUHWExceptionHandler.from_cfg({"bus": "log"})
    exc = FakeHwExc(2)
    assert handler.handle_error(exc) is True
    # abort
    handler = CPUHWExceptionHandler.from_cfg({"bus": "abort"})
    exc = FakeHwExc(2)
    assert handler.handle_error(exc) is False
