from amitools.fs.MetaInfoFSUAE import MetaInfoFSUAE


def fs_metainfofsuae_is_file_test():
    assert MetaInfoFSUAE.is_meta_file("bla.uaem")
    assert not MetaInfoFSUAE.is_meta_file("bla.txt")


def check_parse(line):
    mif = MetaInfoFSUAE()
    mi = mif.parse_data(line)
    assert mi
    line_g = mif.generate_data(mi)
    assert line_g == line


def fs_metainfofsuae_parse_test():
    check_parse("----rwed 2019-02-22 22:36:14.24 \n")
    check_parse("hspa---- 2019-01-31 08:36:14.24 bla fasel\n")


def check_file(path, line):
    mif = MetaInfoFSUAE()
    mi = mif.parse_data(line)
    mif.save_meta(path, mi)
    mi2 = mif.load_meta(path)
    line_g = mif.generate_data(mi2)
    assert line == line_g


def fs_metinfofsuae_rw_test(tmpdir):
    path = str(tmpdir.join("bla.uaem"))
    check_file(path, "----rwed 2019-02-22 22:36:14.24 \n")
    check_file(path, "hspa---- 2019-01-31 08:36:14.24 bla fasel\n")
