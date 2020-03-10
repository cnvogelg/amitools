#!/usr/bin/env python3

import argparse
import array
import struct

parser = argparse.ArgumentParser(
    description="Patch the bsr.l to bsr.w instructions in an Amiga binary to make it 68000 compatible"
)
parser.add_argument("bin_file", help="AmigaOS binary")
parser.add_argument("off_file", help="Offset file to patch")
parser.add_argument(
    "-a",
    "--add_offset",
    action="store",
    type=int,
    default=0,
    help="add global offset (i.e. hunk begin)",
)
parser.add_argument("-o", "--output", action="store", default=None, help="output file")
args = parser.parse_args()

# read bin_file
bin = open(args.bin_file, "rb")
bin_str = bin.read()
bin_data = array.array("B", bin_str)
bin.close()

add_offset = args.add_offset
nop = 0x4E71  # opcode NOP

# parse offset
off = open(args.off_file, "rb")
for line in off:
    # parse and get address
    parts = line.split()
    addr_str = parts[0]
    addr = int(addr_str, 16) + add_offset

    # read words
    words = struct.unpack_from(">HHh", bin_data, offset=addr)
    opcode = words[0]
    far = words[1]
    distance = words[2]
    # check opcode
    valid = opcode & 0xF0FF
    if valid == 0x60FF:
        # check distance
        if far == 0 or far == 0xFFFF:
            print("OK: %08x  distance: %d" % (addr, distance))
            # patch!
            opcode = opcode & 0xFF00
            struct.pack_into(">HhH", bin_data, addr, opcode, distance, nop)
        else:
            print("INVALID(too far): %08x  %04x  %08x" % (addr, opcode, distance))
    else:
        print("INVALID(no branch): %08x  %04x  %08x" % (addr, opcode, distance))

off.close()

# write output
output = args.output
if output == None:
    output = args.bin_file + ".patched"

print("writing '%s'..." % output, end=" ")
out = open(output, "wb")
bin_data.tofile(out)
out.close()
print("done")
