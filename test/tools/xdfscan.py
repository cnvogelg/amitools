import pytest


@pytest.fixture
def xdfscan(toolrun):
    def run(*args, raw_output=False):
        return toolrun.run_checked("xdfscan", *args, raw_output=raw_output)

    return run


def xdfscan_scan_test(xdfscan):
    xdfscan("disks")
