import pytest

# tag a parameter for full testing
def tag_full(value):
    return pytest.param(value, marks=pytest.mark.full)


AROS_ROM = "roms/aros-20130502.rom"
AROS_EXT = "roms/aros-20130502-ext.rom"

ROM_LIST = (
    tag_full("amiga-boot-a1000.rom"),
    tag_full("amiga-boot-a4091.rom"),
    tag_full("amiga-boot-a590.rom"),
    tag_full("amiga-crt-310-cd32-fmv.rom"),
    tag_full("amiga-os-070.rom"),
    tag_full("amiga-os-100.rom"),
    tag_full("amiga-os-110.rom"),
    tag_full("amiga-os-120.rom"),
    tag_full("amiga-os-130-cdtv-ext.rom"),
    "amiga-os-130.rom",
    tag_full("amiga-os-140-a3000.rom"),
    tag_full("amiga-os-204.rom"),
    "amiga-os-205.rom",
    tag_full("amiga-os-300.rom"),
    "amiga-os-310-a1200.rom",
    "amiga-os-310-a3000.rom",
    "amiga-os-310-a4000.rom",
    "amiga-os-310-a500.rom",
    "amiga-os-310-cd32-ext.rom",
    "amiga-os-310-cd32.rom",
    tag_full("amiga-os-320-walker.rom"),
    tag_full("amiga-os-3x0-a4000.rom"),
    "aros-20130502-ext.rom",
    "aros-20130502.rom",
    tag_full("logica-dialoga-200.rom"),
)

SPLIT_ROM = (
    tag_full("amiga-os-204.rom"),
    "amiga-os-205.rom",
    "amiga-os-310-a1200.rom",
    "amiga-os-310-a3000.rom",
    "amiga-os-310-a4000.rom",
    "amiga-os-310-a500.rom",
    "amiga-os-310-cd32.rom",
    tag_full("amiga-os-3x0-a4000.rom"),
)

SPLIT_EXT = (
    "amiga-crt-310-cd32-fmv.rom",
    "amiga-os-130-cdtv-ext.rom",
    "amiga-os-310-cd32-ext.rom",
)


@pytest.fixture(params=ROM_LIST)
def rom_file(request, toolrun):
    rom = "roms/" + request.param
    toolrun.skip_if_data_file_not_available(rom)
    return rom


@pytest.fixture(params=SPLIT_ROM)
def split_rom_file(request, toolrun):
    rom = "roms/" + request.param
    toolrun.skip_if_data_file_not_available(rom)
    return rom


@pytest.fixture(params=SPLIT_EXT)
def split_ext_file(request, toolrun):
    rom = "roms/" + request.param
    toolrun.skip_if_data_file_not_available(rom)
    return rom


def romtool_info_test(toolrun, rom_file):
    toolrun.run_checked("romtool", "info", rom_file)


def romtool_split_build_rom_test(toolrun, split_rom_file, tmpdir):
    toolrun.run_checked(
        "romtool", "split", "-o", str(tmpdir), "--no-version-dir", split_rom_file
    )
    index_txt = str(tmpdir / "index.txt")
    new_rom = str(tmpdir / "new.rom")
    toolrun.run_checked("romtool", "build", "-o", new_rom, index_txt)
    toolrun.run_checked("romtool", "info", new_rom)


def romtool_combine_test(toolrun, tmpdir):
    rom = "amiga-os-310-cd32.rom"
    ext = "amiga-os-310-cd32-ext.rom"
    toolrun.skip_if_data_file_not_available(rom)
    toolrun.skip_if_data_file_not_available(ext)

    new_rom = str(tmpdir / "new.rom")
    toolrun.run_checked("romtool", "combine", "-o", new_rom, rom, ext)
    toolrun.run_checked("romtool", "info", new_rom)


def romtool_diff_test(toolrun):
    toolrun.run_checked("romtool", "diff", AROS_EXT, AROS_ROM)


def romtool_dump_test(toolrun, rom_file):
    toolrun.run_checked("romtool", "dump", rom_file)


def romtool_list_test(toolrun):
    toolrun.run_checked("romtool", "list")


def romtool_patches_test(toolrun):
    toolrun.run_checked("romtool", "patches")


def romtool_patch_test(toolrun, tmpdir):
    rom = "amiga-os-310-a1200.rom"
    toolrun.skip_if_data_file_not_available(rom)

    new_rom = str(tmpdir / "new.rom")
    toolrun.run_checked("romtool", "patch", "-o", new_rom, rom, "1mb_rom")
    toolrun.run_checked("romtool", "patch", "-o", new_rom, rom, "boot_con:name=UCO")


def romtool_query_test(toolrun, rom_file):
    ret, _, stderr = toolrun.run("romtool", "query", rom_file)
    assert ret == 0 or ret == 100
    if ret == 0:
        assert stderr == []


def romtool_scan_test(toolrun, rom_file):
    ret, _, stderr = toolrun.run("romtool", "scan", rom_file)
    assert ret == 0 or ret == 1
    if ret == 0:
        assert stderr == []


def romtool_copy_test(toolrun, tmpdir, rom_file):
    new_rom = str(tmpdir / "new.rom")
    toolrun.run_checked("romtool", "copy", rom_file, new_rom)
