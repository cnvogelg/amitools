import pytest
from amitools.state import ASFFile, ASFParser, MemChunk, MemType, ROMChunk

ASF_LIST = (
    "a500.uss",
    "a500z2ram.uss",
    "a4000.uss",
    "a4000z3ram.uss",
)


@pytest.fixture(params=ASF_LIST)
def asf_file(request):
    file_name = request.param
    return "state/" + file_name


def asf_parser_test(asf_file):
    asf = ASFFile(asf_file)
    parser = ASFParser(asf)
    ram = parser.get_ram_layout()
    assert len(ram) > 0
    ram2 = parser.get_ram_layout(True)
    assert len(ram) == len(ram2)
    roms = parser.get_roms()
    assert len(roms) == 2
    assert roms[0].address == 0xF80000
    assert roms[1].address == 0xF00000


def asf_parser_mem_layout_a500_test():
    asf = ASFFile("state/a500.uss")
    parser = ASFParser(asf)
    ram = parser.get_ram_layout()
    assert ram == [
        MemChunk(0, 512 * 1024, MemType.CHIP),
        MemChunk(0xC00000, 512 * 1024, MemType.BOGO),
    ]


def asf_parser_mem_layout_a500z2ram_test():
    asf = ASFFile("state/a500z2ram.uss")
    parser = ASFParser(asf)
    ram = parser.get_ram_layout()
    assert ram == [
        MemChunk(0, 512 * 1024, MemType.CHIP),
        MemChunk(0xC00000, 512 * 1024, MemType.BOGO),
        MemChunk(0x200000, 0x100000, MemType.Z2RAM),
    ]


def asf_parser_mem_layout_a4000_test():
    asf = ASFFile("state/a4000.uss")
    parser = ASFParser(asf)
    ram = parser.get_ram_layout()
    assert ram == [
        MemChunk(0, 2048 * 1024, MemType.CHIP),
        MemChunk(0x7800000, 8 * 1024 * 1024, MemType.A3KLO),
    ]


def asf_parser_mem_layout_a4000z3ram_test():
    asf = ASFFile("state/a4000z3ram.uss")
    parser = ASFParser(asf)
    ram = parser.get_ram_layout()
    assert ram == [
        MemChunk(0, 2048 * 1024, MemType.CHIP),
        MemChunk(0x7800000, 8 * 1024 * 1024, MemType.A3KLO),
        MemChunk(0x40000000, 16 * 1024 * 1024, MemType.Z3RAM),
    ]
