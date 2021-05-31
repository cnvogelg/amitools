#!/usr/bin/env python3
#
# hunktool
#
# the swiss-army knife for Amiga Hunk executable file format
#
# written by Christian Vogelgsang (chris@vogelgsang.org)

import sys
import argparse
import pprint
import time

from amitools.scan.FileScanner import FileScanner
from amitools.scan.ADFSScanner import ADFSScanner
from amitools.scan.ArchiveScanner import ZipScanner, LhaScanner
from amitools.binfmt.hunk import Hunk
from amitools.binfmt.hunk import HunkReader
from amitools.binfmt.hunk import HunkShow
from amitools.binfmt.hunk import HunkRelocate
import amitools.binfmt.elf
from amitools.util.HexDump import *


def print_pretty(data):
    pp = pprint.PrettyPrinter(indent=2)
    pp.pprint(data)


# ----- commands -------------------------------------------------------------


class HunkCommand:
    def __init__(self, args):
        self.counts = {}
        self.args = args
        self.failed_files = []

    def handle_file(self, path, hunk_file, error_code, delta):
        if error_code not in self.counts:
            self.counts[error_code] = 0
        self.counts[error_code] += 1

        print("%s (%.4fs)" % (path, delta), end=" ")

        # abort if hunk parser failed!
        if error_code != Hunk.RESULT_OK:
            print(Hunk.result_names[error_code], hunk_file.error_string)
            if self.args.dump:
                print_pretty(hunk_file.hunks)
            self.failed_files.append((path, "READ: " + hunk_file.error_string))
            return not self.args.stop

        # if verbose then print block structure
        if self.args.verbose:
            print()
            print("  hunks:    ", hunk_file.get_hunk_summary())
            if self.args.dump:
                print_pretty(hunk_file.hunks)
            print("  type:     ", end=" ")

        # build segments from hunks
        ok = hunk_file.build_segments()
        if not ok:
            print("BUILD SEGMENTS FAILED: %s" % (hunk_file.error_string))
            self.failed_files.append((path, "BUILD: " + hunk_file.error_string))
            return not self.args.stop

        # print recognized file type name
        print(Hunk.type_names[hunk_file.type], end=" ")

        # if verbose then print hunk structure
        if self.args.verbose:
            print()
            print("  segments: ", hunk_file.get_segment_summary())
            print("  overlays: ", hunk_file.get_overlay_segment_summary())
            print("  libs:     ", hunk_file.get_libs_summary())
            print("  units:    ", hunk_file.get_units_summary())
            if self.args.dump:
                print_pretty(hunk_file.hunks)
        else:
            print()

        # do special processing on hunk file for command
        ok = self.handle_hunk_file(path, hunk_file)
        return ok

    def result(self):
        for code in list(self.counts.keys()):
            print(Hunk.result_names[code], ":", self.counts[code])
        for failed in self.failed_files:
            print(failed[0], failed[1])
        return 0

    def process_file(self, scan_file):
        path = scan_file.get_path()
        fobj = scan_file.get_fobj()
        hunk_file = HunkReader.HunkReader()
        start = time.perf_counter()
        result = hunk_file.read_file_obj(path, fobj)
        end = time.perf_counter()
        delta = end - start
        # ignore non hunk files
        if result == Hunk.RESULT_NO_HUNK_FILE:
            return True
        return self.handle_file(path, hunk_file, result, delta)

    def run(self):
        # setup error handler
        def error_handler(sf, e):
            print("FAILED", sf.get_path(), e)
            return not self.args.stop

        def warning_handler(sf, msg):
            print("WARNING", sf.get_path(), msg)

        # setup scanners
        scanners = [ADFSScanner(), ZipScanner(), LhaScanner()]
        scanner = FileScanner(
            self.process_file,
            error_handler=error_handler,
            warning_handler=warning_handler,
            scanners=scanners,
        )
        for path in self.args.files:
            ok = scanner.scan(path)
            if not ok:
                print("ABORTED")
                return False
        return True


# ----- Validator -----


class Validator(HunkCommand):
    def handle_hunk_file(self, path, hunk_file):
        # do nothing extra
        return True


# ----- Info -----


class Info(HunkCommand):
    def handle_hunk_file(self, path, hunk_file):
        args = self.args
        # verbose all hunk
        hs = HunkShow.HunkShow(
            hunk_file,
            show_relocs=args.show_relocs,
            show_debug=args.show_debug,
            disassemble=args.disassemble,
            disassemble_start=args.disassemble_start,
            cpu=args.cpu,
            hexdump=args.hexdump,
            brief=args.brief,
        )
        hs.show_segments()
        return True


# ----- Relocate -----


class Relocate(HunkCommand):
    def handle_hunk_file(self, path, hunk_file):
        if hunk_file.type != Hunk.TYPE_LOADSEG:
            print("ERROR: can only relocate LoadSeg()able files:", path)
            return False

        rel = HunkRelocate.HunkRelocate(hunk_file, verbose=self.args.verbose)
        # get sizes of all segments
        sizes = rel.get_sizes()
        # calc begin addrs for all segments
        base_addr = self.args.base_address
        addrs = rel.get_seq_addrs(base_addr)
        # relocate and return data of segments
        datas = rel.relocate(addrs)
        if datas == None:
            print("ERROR: relocation failed:", path)
            return False
        else:
            print("Relocate to base address", base_addr)
            print("Bases: ", " ".join(["%06x" % (x) for x in addrs]))
            print("Sizes: ", " ".join(["%06x" % (x) for x in sizes]))
            print("Data:  ", " ".join(["%06x" % (len(x)) for x in datas]))
            print("Total: ", "%06x" % (rel.get_total_size()))
            if args.hexdump:
                for d in datas:
                    print_hex(d)
            return True


# ----- Elf2Hunk -----


class ElfInfo:
    def __init__(self, args):
        self.args = args

    def run(self):
        for f in args.files:
            reader = amitools.binfmt.elf.ELFReader()
            elf = reader.load(open(f, "rb"))
            if elf is None:
                print("ERROR loading ELF:", elf.error_string)
                return 1
            dumper = amitools.binfmt.elf.ELFDumper(elf)
            dumper.dump_sections(
                show_relocs=args.show_relocs, show_debug=args.show_debug
            )
            dumper.dump_symbols()
            dumper.dump_relas()
        return 0


# ----- main -----
def main(args=None):
    # call scanner and process all files with selected command
    cmd_map = {
        "validate": Validator,
        "info": Info,
        "elfinfo": ElfInfo,
        "relocate": Relocate,
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="command: " + ",".join(list(cmd_map.keys())))
    parser.add_argument("files", nargs="+")
    parser.add_argument(
        "-d",
        "--dump",
        action="store_true",
        default=False,
        help="dump the hunk structure",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False, help="be more verbos"
    )
    parser.add_argument(
        "-s", "--stop", action="store_true", default=False, help="stop on error"
    )
    parser.add_argument(
        "-R",
        "--show-relocs",
        action="store_true",
        default=False,
        help="show relocation entries",
    )
    parser.add_argument(
        "-D",
        "--show-debug",
        action="store_true",
        default=False,
        help="show debug info entries",
    )
    parser.add_argument(
        "-A",
        "--disassemble",
        action="store_true",
        default=False,
        help="disassemble code segments",
    )
    parser.add_argument(
        "-S",
        "--disassemble-start",
        action="store",
        type=int,
        default=0,
        help="start address for dissassembly",
    )
    parser.add_argument(
        "-x",
        "--hexdump",
        action="store_true",
        default=False,
        help="dump segments in hex",
    )
    parser.add_argument(
        "-b",
        "--brief",
        action="store_true",
        default=False,
        help="show only brief information",
    )
    parser.add_argument(
        "-B",
        "--base-address",
        action="store",
        type=int,
        default=0,
        help="base address for relocation",
    )
    parser.add_argument(
        "-c",
        "--cpu",
        action="store",
        default="68000",
        help="disassemble for given cpu (objdump only)",
    )
    args = parser.parse_args(args=args)

    cmd = args.command
    if cmd not in cmd_map:
        print("INVALID COMMAND:", cmd)
        print("valid commands are:")
        for a in cmd_map:
            print("  ", a)
        return 1
    cmd_cls = cmd_map[cmd]

    # execute command
    cmd = cmd_cls(args)
    res = cmd.run()
    return res


if __name__ == "__main__":
    sys.exit(main())
