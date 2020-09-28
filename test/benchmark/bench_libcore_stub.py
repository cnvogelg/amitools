import logging
import pytest

from amitools.vamos.libcore import LibStubGen, LibCtx, LibImplScanner
from amitools.vamos.lib.VamosTestLibrary import VamosTestLibrary
from amitools.vamos.machine import MockMachine
from amitools.vamos.libcore import LibProfileData
from amitools.fd import read_lib_fd


def _create_ctx():
    machine = MockMachine()
    return LibCtx(machine)


def _create_stub(do_profile=False, do_log=False):
    name = "vamostest.library"
    impl = VamosTestLibrary()
    fd = read_lib_fd(name)
    scanner = LibImplScanner()
    scan = scanner.scan(name, impl, fd)
    ctx = _create_ctx()
    if do_profile:
        profile = LibProfileData(fd)
    else:
        profile = None
    if do_log:
        log_missing = logging.getLogger("missing")
        log_valid = logging.getLogger("valid")
    else:
        log_missing = None
        log_valid = None
    # create stub
    gen = LibStubGen(log_missing=log_missing, log_valid=log_valid)
    stub = gen.gen_stub(scan, ctx, profile)
    return stub


def libcore_stub_base_benchmark(benchmark):
    stub = _create_stub()
    benchmark(stub.PrintHello)


def libcore_stub_profile_benchmark(benchmark):
    stub = _create_stub(do_profile=True)
    benchmark(stub.PrintHello)


def libcore_stub_log_benchmark(benchmark):
    stub = _create_stub(do_log=True)
    benchmark(stub.PrintHello)


def libcore_stub_log_profile_benchmark(benchmark):
    stub = _create_stub(do_profile=True, do_log=True)
    benchmark(stub.PrintHello)
