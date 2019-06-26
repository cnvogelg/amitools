from amitools.binfmt.elf.BinFmtELF import BinFmtELF


def binfmt_elf_check_elf_test():
    bfe = BinFmtELF()
    assert bfe.is_image("bin/test_hello_agcc")
    bin_img = bfe.load_image("bin/test_hello_agcc")
    assert bin_img is not None
    secs = bin_img.get_segments()
    assert len(secs) > 0
