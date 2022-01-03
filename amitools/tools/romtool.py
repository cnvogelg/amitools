#!/usr/bin/env python3
# romtool
#
# work with Amiga ROM files aka Kickstarts

import sys
import argparse
import os
import logging

from amitools.util.Logging import setup_logging, add_logging_options
from amitools.util.HexDump import print_hex_diff, print_hex
import amitools.util.KeyValue as KeyValue
import amitools.rom as rom
from amitools.binfmt.hunk.BinFmtHunk import BinFmtHunk
from amitools.binfmt.BinFmt import BinFmt


DESC = """romtool allows you to dissect, inspect, or create Amiga ROM files"""


def do_list_cmd(args):
    rs = rom.RomSplitter()
    rs.list_roms(print, args.rom, show_entries=args.modules)
    return 0


def do_query_cmd(args):
    ri = args.rom_image
    rs = rom.RomSplitter()
    if not rs.find_rom(ri):
        print(ri, "not found in split database!")
        return 100
    else:
        rs.print_rom(print)
        if args.modules is None:
            e = rs.get_all_entries()
        else:
            e = rs.query_entries(args.modules)
        rs.print_entries(print, e)
        return 0


def do_split_cmd(args):
    ri = args.rom_image
    rs = rom.RomSplitter()
    rom_img = rs.find_rom(ri)
    if rom_img is None:
        logging.error("'%s' was not found in split database!", ri)
        return 100
    else:
        rs.print_rom(logging.info)
        # no output dir? end now
        out_path = args.output_dir
        if out_path is None:
            return 0
        # get modules to export
        if args.modules is None:
            entries = rs.get_all_entries()
        else:
            entries = rs.query_entries(args.modules)
        # setup output dir
        if not args.no_version_dir:
            out_path = os.path.join(out_path, rom_img.short_name)
        # make dirs
        if not os.path.isdir(out_path):
            logging.info("creating directory '%s'", out_path)
            os.makedirs(out_path)
        # create index file
        if not args.no_index:
            idx_path = os.path.join(out_path, "index.txt")
            logging.info("writing index to '%s'", idx_path)
            rs.write_index_file(idx_path)
        # extract entries
        logging.debug("extract module: fixes=%s, patches=%s", args.fixes, args.patches)
        bfh = BinFmtHunk()
        for e in entries:
            rs.print_entry(logging.info, e)
            bin_img = rs.extract_bin_img(e, args.fixes, args.patches)
            out_file = os.path.join(out_path, e.name)
            logging.info("writing file '%s'", out_file)
            bfh.save_image(out_file, bin_img)
        return 0


def do_build_cmd(args):
    # get options
    rom_size = args.rom_size
    kick_addr = int(args.kick_addr, 16)
    ext_addr = int(args.ext_addr, 16)
    kickety_split = args.kickety_split
    rom_type = args.rom_type
    fill_byte = int(args.fill_byte, 16)
    rom_rev = args.rom_rev
    if rom_rev is not None:
        rom_rev = list(map(int, rom_rev.split(".")))
    add_footer = args.add_footer
    # select rom builder
    if rom_type == "kick":
        logging.info("building %d KiB Kick ROM @%08x", rom_size, kick_addr)
        rb = rom.KickRomBuilder(
            rom_size,
            base_addr=kick_addr,
            fill_byte=fill_byte,
            kickety_split=kickety_split,
            rom_ver=rom_rev,
        )
    elif rom_type == "ext":
        logging.info(
            "building %d KiB Ext ROM @%08x Rev %r for Kick @%08x",
            rom_size,
            ext_addr,
            rom_rev,
            kick_addr,
        )
        rb = rom.ExtRomBuilder(
            rom_size,
            base_addr=ext_addr,
            fill_byte=fill_byte,
            add_footer=add_footer,
            rom_ver=rom_rev,
            kick_addr=kick_addr,
        )
    else:
        logging.error("Unknown rom_type=%s", rom_type)
        return 1
    # build file list
    if args.modules is None:
        logging.error("No modules given!")
        return 1
    file_list = rb.build_file_list(args.modules)
    # load modules
    bf = BinFmt()
    for f in file_list:
        logging.info("adding file '%s'", f)
        name = os.path.basename(f)
        # load image
        if bf.is_image(f):
            bin_img = bf.load_image(f)
            # is it a blizkick module?
            bkm = rom.BlizKickModule(bin_img)
            if bkm.get_type() == "module":
                bkm.fix_module()
            elif bkm.get_type() == "patch":
                logging.error("BlizKick Patches are not supported, yet: %s", name)
                return 5
            # get image params
            size = bin_img.get_size()
            data = None
        else:
            # load raw data
            bin_img = None
            with open(f, "rb") as fh:
                data = fh.read()
            size = len(data)

        # calc long word padding
        padding = 0
        if size & 3 != 0:
            padding = 4 - size & 3

        # handle kickety split
        if kickety_split and rb.cross_kickety_split(size + padding):
            off = rb.get_rom_offset()
            logging.info("@%08x: adding kickety split", off)
            rb.add_kickety_split()

        off = rb.get_rom_offset()
        # add image
        if bin_img is not None:
            logging.info("@%08x: adding module '%s'", off, f)
            e = rb.add_bin_img(name, bin_img)
            if e is None:
                logging.error(
                    "@%08x: can't add module '%s': %s", off, f, rb.get_error()
                )
                return 3
        # add data
        else:
            logging.info("@%08x: adding raw data '%s'", off, f)
            e = rb.add_module(name, data)
            if e is None:
                logging.error(
                    "@%08x: can't add raw data '%s': %s", off, f, rb.get_error()
                )
                return 3

        # add long word padding?
        if padding != 0:
            off = rb.get_rom_offset()
            logging.info("@%08x: adding padding: +%d" % (off, padding))
            e = rb.add_padding(padding)
            if e is None:
                logging.error("@%08x: can't add padding: %s", off, rb.get_error())
                return 3

    # build rom
    off = rb.get_rom_offset()
    logging.info(
        "@%08x: padding %d bytes with %02x", off, rb.get_bytes_left(), fill_byte
    )
    rom_data = rb.build_rom()
    if rom_data is None:
        logging.error("building ROM failed: %s", rb.get_error())
        return 4

    # save rom
    output = args.output
    if output is not None:
        logging.info("saving ROM to '%s'", output)
        with open(output, "wb") as fh:
            fh.write(rom_data)
    return 0


def do_diff_cmd(args):
    # load ROMs
    img_a = args.image_a
    logging.info("loading ROM A from '%s'", img_a)
    rom_a = rom.Loader.load(img_a)
    img_b = args.image_b
    logging.info("loading ROM B from '%s'", img_b)
    rom_b = rom.Loader.load(img_b)
    # check sizes
    size_a = len(rom_a)
    size_b = len(rom_b)
    if not args.force and size_a != size_b:
        logging.error("ROM differ in size (%08x != %08x). Aborting", size_a, size_b)
        return 2
    # do diff
    base_addr = 0
    if args.rom_addr:
        base_addr = int(args.rom_addr, 16)
    elif args.show_address:
        kh = rom.KickRomAccess(rom_a)
        if kh.is_kick_rom():
            base_addr = kh.get_base_addr()
        else:
            logging.error("Not a KickROM! Can't detect base address.")
            return 3
    print_hex_diff(
        rom_a, rom_b, num=args.columns, show_same=args.same, base_addr=base_addr
    )
    return 0


def do_dump_cmd(args):
    img = args.image
    logging.info("loading ROM from '%s'", img)
    rom_img = rom.Loader.load(img)
    base_addr = 0
    if args.rom_addr:
        base_addr = int(args.rom_addr, 16)
    elif args.show_address:
        kh = rom.KickRomAccess(rom_img)
        if kh.is_kick_rom():
            base_addr = kh.get_base_addr()
        else:
            logging.error("Not a KickROM! Can't detect base address.")
            return 3
    print_hex(rom_img, num=args.columns, base_addr=base_addr)
    return 0


def do_copy_cmd(args):
    in_img = args.in_image
    logging.info("loading ROM from '%s'", in_img)
    rom_img = rom.Loader.load(in_img)
    kh = rom.KickRomAccess(rom_img)
    if args.fix_checksum:
        kh.make_writable()
        kh.write_check_sum()
    out_img = args.out_image
    logging.info("saving ROM to '%s'", out_img)
    with open(out_img, "wb") as fh:
        fh.write(kh.get_data())
    return 0


def do_info_cmd(args):
    img = args.image
    rom_img = rom.Loader.load(img)
    kh = rom.KickRomAccess(rom_img)
    checks = [
        ("size", kh.check_size()),
        ("header", kh.check_header()),
        ("footer", kh.check_footer()),
        ("size_field", kh.check_size()),
        ("chk_sum", kh.verify_check_sum()),
        ("kickety_split", kh.check_kickety_split()),
        ("magic_reset", kh.check_magic_reset()),
        ("is_kick", kh.is_kick_rom()),
    ]
    c = ["%-20s  %s" % (x[0], "ok" if x[1] else "NOK") for x in checks]
    for i in c:
        print(i)
    values = [
        ("check_sum", "%08x", kh.read_check_sum()),
        ("base_addr", "%08x", kh.get_base_addr()),
        ("boot_pc", "%08x", kh.read_boot_pc()),
        ("rom_rev", "%d.%d", kh.read_rom_ver_rev()),
        ("exec_rev", "%d.%d", kh.read_exec_ver_rev()),
    ]
    v = ["%-20s  %s" % (x[0], x[1] % x[2]) for x in values]
    for i in v:
        print(i)
    return 0


def do_patch_cmd(args):
    img = args.image
    logging.info("loading ROM from '%s'", img)
    rom_img = rom.Loader.load(img)
    # is kick?
    kh = rom.KickRomAccess(rom_img)
    is_kick = kh.is_kick_rom()
    # apply patches
    rp = rom.RomPatcher(rom_img)
    for patch in args.patches:
        name, patch_args = KeyValue.parse_name_args_string(patch)
        logging.info("searching patch '%s' -> %s %s", patch, name, patch_args)
        p = rp.find_patch(name)
        if p is None:
            logging.error("can't find patch '%s'", name)
            return 1
        ok = rp.apply_patch(p, patch_args)
        if ok:
            logging.info("applied patch '%s'", name)
        else:
            logging.error("error applying patch '%s'", name)
            return 2
    # update kick sum
    rom_data = rp.get_patched_rom()
    if is_kick:
        kh = rom.KickRomAccess(rom_data)
        cs = kh.write_check_sum()
        logging.info("updated kicksum=%08x", cs)
    # save rom
    output = args.output
    if output is not None:
        logging.info("saving ROM to '%s'", output)
        with open(output, "wb") as fh:
            fh.write(rom_data)
    return 0


def do_patches_cmd(args):
    for p in rom.RomPatcher.patches:
        print("%-10s  %s" % (p.name, p.desc))
        args_desc = p.args_desc
        if args_desc is not None:
            for ad in args_desc:
                print("%10s    %-10s  %s" % ("", ad, args_desc[ad]))
    return 0


def do_combine_cmd(args):
    # load kick rom
    kick_img = args.kick_rom
    logging.info("loading Kick ROM from '%s'", kick_img)
    kick_rom = rom.Loader.load(kick_img)
    # load ext rom
    ext_img = args.ext_rom
    logging.info("loading Ext ROM from '%s'", ext_img)
    ext_rom = rom.Loader.load(ext_img)
    # check kick
    logging.info("validating Kick ROM")
    ka = rom.KickRomAccess(kick_rom)
    if not ka.is_kick_rom():
        logging.error("Not a Kick ROM image!")
        return 1
    if ka.get_size_kib() != 512:
        logging.error("Not a 512 KiB Kick ROM image!")
        return 2
    if ka.get_base_addr() != 0xF80000:
        logging.error("Kick ROM base address is not 0xf80000!")
        return 3
    # check ext
    logging.info("validating Ext ROM")
    ka = rom.KickRomAccess(ext_rom)
    if not ka.check_header():
        logging.error("No ROM Header in Ext ROM image found!")
    if (
        ka.get_size_kib() != 512
        and ka.get_size_kib() != 1536
        and ka.get_size_kib() != 3584
    ):
        logging.error("Not a 512/1536/3584 KiB Ext ROM image!")
    # write rom
    rom_img = ext_rom + kick_rom
    output = args.output
    if output is not None:
        logging.info("saving ROM to '%s'", output)
        with open(output, "wb") as fh:
            fh.write(rom_img)
    return 0


def do_scan_cmd(args):
    # load rom
    img = args.image
    logging.info("loading ROM from '%s'", img)
    rom_img = rom.Loader.load(img)
    # scan
    base_addr = args.rom_addr
    if base_addr is not None:
        base_addr = int(base_addr, 16)
        logging.info("set base address: %08x", base_addr)
    else:
        # guess address
        rs = rom.ResidentScan(rom_img)
        base_addr = rs.guess_base_addr()
        if base_addr is None:
            logging.error("can't guess base address of ROM!")
            return 1
        elif type(base_addr) is list:
            addrs = list(map(hex, base_addr))
            logging.error("multiple addresses guessed: %s", ",".join(addrs))
            return 2
        else:
            logging.info("guessed base address: %08x", base_addr)
    # setup scanner
    rs = rom.ResidentScan(rom_img, base_addr)
    offs = rs.get_all_resident_pos()
    info = args.show_info
    for off in offs:
        r = rs.get_resident(off)
        nt = r.get_node_type_str()
        if r.name:
            name = r.name.strip()
        else:
            name = '""'
        if r.id_string:
            id_string = r.id_string.strip()
        else:
            id_string = '""'
        if info:
            print("@%08x  name:       %s" % (off, name))
            spc = " " * 10
            print(spc, "id_string:  %s" % id_string)
            print(spc, "node_type:  %s" % nt)
            print(spc, "flags:      %s" % (" | ".join(r.get_flags_strings())))
            print(spc, "version:    %u" % r.version)
            print(spc, "priority:   %d" % r.pri)
            print(spc, "init off:   %08x" % r.init_off)
            print(spc, "skip off:   %08x" % r.skip_off)
        else:
            print(
                "@%08x  +%08x  %-12s  %+4d  %s  %s"
                % (off, r.skip_off, nt, r.pri, name, id_string)
            )
    return 0


def setup_list_parser(parser):
    parser.add_argument("-r", "--rom", default=None, help="query rom name by wildcard")
    parser.add_argument(
        "-m",
        "--modules",
        default=False,
        action="store_true",
        help="show entries of ROMs",
    )
    parser.set_defaults(cmd=do_list_cmd)


def setup_query_parser(parser):
    parser.add_argument("rom_image", help="rom image to be checked")
    parser.add_argument(
        "-m", "--modules", default=None, help="query module by wildcard"
    )
    parser.set_defaults(cmd=do_query_cmd)


def setup_split_parser(parser):
    parser.add_argument("rom_image", help="rom image file to be split")
    parser.add_argument("-o", "--output-dir", help="store modules in this base dir")
    parser.add_argument(
        "-m", "--modules", default=None, help="query module by wildcard"
    )
    parser.add_argument(
        "--no-version-dir",
        default=False,
        action="store_true",
        help="do not create sub directory with version name",
    )
    parser.add_argument(
        "--no-index",
        default=False,
        action="store_true",
        help="do not create an 'index.txt' in output path",
    )
    parser.add_argument(
        "-p",
        "--patches",
        default=False,
        action="store_true",
        help="apply optional patches to modules",
    )
    parser.add_argument(
        "-f",
        "--no-fixes",
        dest="fixes",
        default=True,
        action="store_false",
        help="do not apply available fixes to modules",
    )
    parser.set_defaults(cmd=do_split_cmd)


def setup_build_parser(parser):
    parser.add_argument(
        "modules",
        default=None,
        nargs="+",
        help="modules or index.txt files to be added",
    )
    parser.add_argument("-o", "--output", help="rom image file to be built")
    parser.add_argument(
        "-t", "--rom-type", default="kick", help="what type of ROM to build (kick, ext)"
    )
    parser.add_argument(
        "-s", "--rom-size", default=512, type=int, help="size of ROM in KiB"
    )
    parser.add_argument(
        "-a", "--kick-addr", default="f80000", help="base address of Kick ROM in hex"
    )
    parser.add_argument(
        "-e", "--ext-addr", default="e00000", help="base address of Ext ROM in hex"
    )
    parser.add_argument(
        "-f",
        "--add-footer",
        default=False,
        action="store_true",
        help="add footer with check sum to Ext ROM",
    )
    parser.add_argument(
        "-r", "--rom-rev", default=None, help="set ROM revision, e.g. 45.10"
    )
    parser.add_argument(
        "-k",
        "--kickety_split",
        default=False,
        action="store_true",
        help="add 'kickety split' romhdr at center of ROM",
    )
    parser.add_argument(
        "-b", "--fill-byte", default="ff", help="fill byte in hex for empty ranges"
    )
    parser.set_defaults(cmd=do_build_cmd)


def setup_diff_parser(parser):
    parser.add_argument("image_a", help="rom image a")
    parser.add_argument("image_b", help="rom image b")
    parser.add_argument(
        "-s",
        "--same",
        default=False,
        action="store_true",
        help="show same lines of ROMs",
    )
    parser.add_argument(
        "-a",
        "--show-address",
        default=False,
        action="store_true",
        help="show KickROM address (otherwise image offset)",
    )
    parser.add_argument(
        "-b", "--rom-addr", default=None, help="use hex base address for output"
    )
    parser.add_argument(
        "-f",
        "--force",
        default=False,
        action="store_true",
        help="diff ROMs even if size differs",
    )
    parser.add_argument(
        "-c", "--columns", default=8, type=int, help="number of bytes shown per line"
    )
    parser.set_defaults(cmd=do_diff_cmd)


def setup_dump_parser(parser):
    parser.add_argument("image", help="rom image to be dumped")
    parser.add_argument(
        "-a",
        "--show-address",
        default=False,
        action="store_true",
        help="show KickROM address (otherwise image offset)",
    )
    parser.add_argument(
        "-b", "--rom-addr", default=None, help="use hex base address for output"
    )
    parser.add_argument(
        "-c", "--columns", default=16, type=int, help="number of bytes shown per line"
    )
    parser.set_defaults(cmd=do_dump_cmd)


def setup_info_parser(parser):
    parser.add_argument("image", help="rom image to be analyzed")
    parser.set_defaults(cmd=do_info_cmd)


def setup_patch_parser(parser):
    parser.add_argument("image", help="rom image to be patched")
    parser.add_argument(
        "patches",
        default=None,
        nargs="+",
        help="patches to be applied: name[:arg1[=val1],...]",
    )
    parser.add_argument("-o", "--output", help="rom image file to be built")
    parser.set_defaults(cmd=do_patch_cmd)


def setup_patches_parser(parser):
    parser.set_defaults(cmd=do_patches_cmd)


def setup_combine_parser(parser):
    parser.add_argument("kick_rom", help="kick rom to be combined")
    parser.add_argument("ext_rom", help="ext rom to be combined")
    parser.set_defaults(cmd=do_combine_cmd)
    parser.add_argument("-o", "--output", help="rom image file to be built")


def setup_scan_parser(parser):
    parser.add_argument("image", help="rom image to be scanned")
    parser.add_argument(
        "-b",
        "--rom-addr",
        default=None,
        help="use this base address for ROM. otherwise guess.",
    )
    parser.add_argument(
        "-i",
        "--show-info",
        default=False,
        action="store_true",
        help="show more details on resident",
    )
    parser.set_defaults(cmd=do_scan_cmd)


def setup_copy_parser(parser):
    parser.add_argument("in_image", help="rom image to read")
    parser.add_argument("out_image", help="rom image to be written")
    parser.add_argument(
        "-c",
        "--fix-checksum",
        default=False,
        action="store_true",
        help="fix checksum on written image",
    )
    parser.set_defaults(cmd=do_copy_cmd)


def parse_args(args=None):
    """parse args and return (args, opts)"""
    parser = argparse.ArgumentParser(description=DESC)

    # global options
    parser.add_argument(
        "-k",
        "--rom-key",
        default="rom.key",
        help="the path of a rom.key file if you want to " "process crypted ROMs",
    )
    add_logging_options(parser)

    # sub parsers
    sub_parsers = parser.add_subparsers(help="sub commands")

    # build
    build_parser = sub_parsers.add_parser("build", help="build a ROM from modules")
    setup_build_parser(build_parser)
    # combine
    combine_parser = sub_parsers.add_parser(
        "combine", help="combine a kick and an ext ROM to a 1 MiB ROM"
    )
    setup_combine_parser(combine_parser)
    # diff
    diff_parser = sub_parsers.add_parser(
        "diff", help="show differences in two ROM images"
    )
    setup_diff_parser(diff_parser)
    # dump
    dump_parser = sub_parsers.add_parser("dump", help="dump a ROM image")
    setup_dump_parser(dump_parser)
    # info
    info_parser = sub_parsers.add_parser("info", help="print infos on a ROM image")
    setup_info_parser(info_parser)
    # list
    list_parser = sub_parsers.add_parser("list", help="list ROMs in split data")
    setup_list_parser(list_parser)
    # patch
    patch_parser = sub_parsers.add_parser("patch", help="patch a ROM image")
    setup_patch_parser(patch_parser)
    # patches
    patches_parser = sub_parsers.add_parser("patches", help="show available patches")
    setup_patches_parser(patches_parser)
    # query
    query_parser = sub_parsers.add_parser("query", help="query if ROM is in split data")
    setup_query_parser(query_parser)
    # scan
    scan_parser = sub_parsers.add_parser("scan", help="scan ROM for residents")
    setup_scan_parser(scan_parser)
    # split
    split_parser = sub_parsers.add_parser("split", help="split a ROM into modules")
    setup_split_parser(split_parser)
    # copy
    copy_parser = sub_parsers.add_parser(
        "copy", help="copy ROM image and fix on the fly"
    )
    setup_copy_parser(copy_parser)

    # parse
    opts = parser.parse_args(args=args)
    if "cmd" not in opts:
        parser.print_help()
        sys.exit(1)
    return opts


# ----- main -----
def main(args=None):
    # parse args and init logging
    opts = parse_args(args)
    setup_logging(opts)
    # say hello
    logging.info("Welcom to romtool")
    # run command
    try:
        result = opts.cmd(opts)
        assert type(result) is int
        return result
    except IOError as e:
        logging.error("IO Error: %s", e)
        return 1


# ----- entry point -----
if __name__ == "__main__":
    sys.exit(main())
