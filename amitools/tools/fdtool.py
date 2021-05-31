#!/usr/bin/env python3
#
# fdtool <file.fd> ...
#

import sys
import argparse

import amitools.fd.FDFormat as FDFormat

# ----- dump -----


def dump(fname, fd, add_private):
    print(fname)
    print(("  base: %s" % fd.get_base_name()))
    funcs = fd.get_funcs()
    num = 1
    for f in funcs:
        if add_private or not f.is_private():
            bias = f.get_bias()
            print(
                (
                    "  #%04d  %5d  0x%04x  %30s %s"
                    % (num, bias, bias, f.get_name(), f.get_arg_str())
                )
            )
            num += 1


# ----- generate -----


def generate_python_code(fd, add_private):
    funcs = fd.get_funcs()
    for f in funcs:
        if add_private or not f.is_private():
            args = f.get_args()
            if len(args) > 0:
                args = tuple(args)
            else:
                args = None
            print("    (%d, '%s', %s)," % (f.get_bias(), f.get_name(), args))


def generate_sasc_code(fname, fd, add_private, prefix=""):
    funcs = fd.get_funcs()
    fo = open(fname, "w")
    for f in funcs:
        if add_private or not f.is_private():
            line = "__asm __saveds int %s%s(" % (prefix, f.get_name())
            args = f.get_args()
            if args != None:
                for a in args:
                    line += "register __%s int %s" % (a[1], a[0])
                    if a != args[-1]:
                        line += ", "
            else:
                line += " void "
            line += " )"
            fo.write(line)
            fo.write("{\n  return 0;\n}\n\n")
    fo.close()


# ----- main -----
def main(args=None):
    # parse args
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument(
        "-P",
        "--add-private",
        action="store_true",
        default=False,
        help="add private functions",
    )
    parser.add_argument(
        "-p",
        "--gen-python",
        action="store_true",
        default=False,
        help="generate python code for vamos",
    )
    parser.add_argument(
        "-f", "--gen-fd", action="store", default=None, help="generate a new fd file"
    )
    parser.add_argument(
        "-c",
        "--gen-sasc",
        action="store",
        default=None,
        help="generate SAS C code file",
    )
    parser.add_argument(
        "-E",
        "--prefix",
        action="store",
        default="",
        help="add prefix to functions in C",
    )
    args = parser.parse_args(args=args)

    # main loop
    files = args.files
    for fname in files:
        fd = FDFormat.read_fd(fname)
        code_gen = False
        if args.gen_python:
            generate_python_code(fd, args.add_private)
            code_gen = True
        if args.gen_sasc:
            generate_sasc_code(args.gen_sasc, fd, args.add_private, args.prefix)
            code_gen = True
        if args.gen_fd != None:
            FDFormat.write_fd(args.gen_fd, fd, args.add_private)
            code_gen = True
        if not code_gen:
            dump(fname, fd, args.add_private)


if __name__ == "__main__":
    main()
