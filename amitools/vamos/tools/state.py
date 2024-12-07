import sys

from .tool import Tool
from amitools.vamos.astructs import AmigaStructTypes, TypeDumper
from amitools.state import ASFFile, ASFParser


class StateTool(Tool):
    def __init__(self):
        Tool.__init__(self, "state", "inspect system state")

    def add_args(self, arg_parser):
        sub = arg_parser.add_subparsers(dest="type_cmd")
        # info
        parser = sub.add_parser("info", help="give info on state file")
        parser.add_argument("file", help="UAE state file (.uss)")
        parser.add_argument(
            "-d", "--dump", default=False, action="store_true", help="dump state file"
        )
        parser.add_argument("-s", "--save", help="save RAM to files with prefix")

    def run(self, args):
        type_cmd = args.type_cmd
        # info
        if type_cmd == "info":
            asf = ASFFile(args.file)
            chunks = asf.chunklist()

            # dump state file?
            if args.dump:
                for chunk in chunks:
                    print(chunk)

            # parse state file
            parser = ASFParser(asf)

            # dump expansion
            if args.dump:
                expansion = parser.get_expansion_ram()
                if expansion:
                    print(expansion)

            # show ram layout
            print("RAM:")
            load_ram = args.save is not None
            ram_layout = parser.get_ram_layout(load_ram)
            for ram in ram_layout:
                if args.save:
                    file = args.save + f".{ram.type.name}.{ram.address:08x}.dump"
                    with open(file, "wb") as fh:
                        fh.write(ram.data)
                else:
                    file = ""
                print(
                    f"@{ram.address:08x}  +{ram.size:08x}  {ram.type.name:6s}  {file}"
                )

            # show roms
            print("ROM:")
            roms = parser.get_roms()
            for rom in roms:
                print(
                    f"@{rom.address:08x}  +{rom.size:08x}  {rom.crc32:08x}  {rom.name}  {rom.path}"
                )

            return 0
