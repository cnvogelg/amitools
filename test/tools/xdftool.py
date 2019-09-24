import pytest

ADF_LIST = (
    "amiga-os-100-workbench.adf",
    "amiga-os-110-workbench.adf",
    "amiga-os-120-workbench.adf",
    "amiga-os-134-extras.adf",
    "amiga-os-134-workbench.adf",
    "amiga-os-200-workbench.adf",
    "amiga-os-204-workbench.adf",
    "amiga-os-210-workbench.adf",
    "amiga-os-300-workbench.adf",
    "amiga-os-310-extras.adf",
    "amiga-os-310-fonts.adf",
    "amiga-os-310-install.adf",
    "amiga-os-310-locale.adf",
    "amiga-os-310-storage.adf",
    "amiga-os-310-workbench.adf",
    "aros-20130502-boot.adf"
)


@pytest.fixture(params=ADF_LIST)
def adf_file(request, toolrun):
    rom = "disks/" + request.param
    toolrun.skip_if_data_file_not_available(rom)
    return rom


def xdftool_list_test(toolrun, adf_file):
    toolrun.run_checked("xdftool", adf_file, "list")
