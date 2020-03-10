from amitools.vamos.machine import DisAsm
from . import Hunk


class HunkDisassembler:
    def __init__(self, cpu="68000"):
        self.disasm = DisAsm.create(cpu)

    def get_symtab(self, hunk):
        for h in hunk[1:]:
            if h["type"] == Hunk.HUNK_SYMBOL:
                return h["symbols"]
        return None

    def find_symbol(self, hunk, offset, always):
        symtab = self.get_symtab(hunk)
        if symtab == None:
            if always:
                return "%08x" % offset
            else:
                return None

        symmap = {}
        for s in symtab:
            symmap[s[1]] = s[0]

        offs = sorted(symmap.keys())
        last = None
        last_offset = 0
        for o in offs:
            if o == offset:
                return symmap[o]

            if always:
                if o < offset:
                    # approximate to last symbol
                    if last != None:
                        return last + " + %08x" % (o - last_offset)
                    else:
                        return "%08x" % offset
            last = symmap[o]
            last_offset = o

        if always:
            return "%08x" % offset
        else:
            return None

    def find_src_line(self, hunk, addr):
        for h in hunk[1:]:
            if h["type"] == Hunk.HUNK_DEBUG and h["debug_type"] == "LINE":
                src_map = h["src_map"]
                for e in src_map:
                    src_line = e[0]
                    src_addr = e[1] + h["debug_offset"]
                    if src_addr == addr:
                        return (h["src_file"], src_line)
        return None

    # map reloc type to number of words to be relocated
    map_reloc_to_num_words = {
        Hunk.HUNK_ABSRELOC32: 2,
        Hunk.HUNK_DREL16: 1,
        Hunk.HUNK_DREL32: 2,
    }

    # find_reloc
    # return
    #   0 - rel_offset to addr reloc begin (in words)
    #   1 - size of reloc (in words)
    #   2 - hunk number reloc references
    #   3 - relative offset in hunk (in bytes)
    #   4 - reloc hunk
    def find_reloc(self, hunk, addr, word):
        end_addr = addr + len(word) * 2
        for h in hunk[1:]:
            valid = h["type"] in self.map_reloc_to_num_words
            if valid:
                num_words = self.map_reloc_to_num_words[h["type"]]
                reloc = h["reloc"]
                for hunk_num in reloc:
                    offsets = reloc[hunk_num]
                    for off in offsets:
                        if off >= addr and off + num_words * 2 <= end_addr:
                            word_offset = (off - addr) // 2  # in words

                            # calc offset
                            addr = 0
                            for i in range(num_words):
                                addr = addr * 0x10000 + word[word_offset + i]

                            reloc_type_name = (
                                h["type_name"].replace("HUNK_", "").lower()
                            )
                            return (
                                word_offset,
                                num_words,
                                hunk_num,
                                addr,
                                reloc_type_name,
                            )
        return None

    map_ext_ref_to_num_words = {
        Hunk.EXT_ABSREF32: 2,
        Hunk.EXT_RELREF16: 1,
        Hunk.EXT_DEXT16: 1,
    }

    # find_ext_ref
    # return
    #   0 - word offset to word begin (in words)
    #   1 - size of reloc (in words)
    #   2 - name of external symbol
    #   3 - type name of ext ref
    def find_ext_ref(self, hunk, addr, word):
        end_addr = addr + len(word) * 2
        for h in hunk[1:]:
            if h["type"] == Hunk.HUNK_EXT:
                for ext in h["ext_ref"]:
                    refs = ext["refs"]
                    valid = ext["type"] in self.map_ext_ref_to_num_words
                    if valid:
                        num_words = self.map_ext_ref_to_num_words[ext["type"]]
                        for ref in refs:
                            if ref >= addr and ref < end_addr:
                                word_offset = (ref - addr) // 2
                                type_name = ext["type_name"].replace("EXT_", "").lower()
                                return (word_offset, num_words, ext["name"], type_name)
        return None

    # search the HUNK_EXT for a defintion
    def find_ext_def(self, hunk, addr):
        for h in hunk[1:]:
            if h["type"] == Hunk.HUNK_EXT:
                for ext in h["ext_def"]:
                    if addr == ext["def"]:
                        return ext["name"]
        return None

    # search the index of a lib for a definition
    def find_index_def(self, hunk, addr):
        main = hunk[0]
        if "index_hunk" in main:
            info = main["index_hunk"]
            if "defs" in info:
                for d in info["defs"]:
                    if d["value"] == addr:
                        return d["name"]
        return None

    def find_symbol_or_def(self, hunk, addr, always):
        symbol = self.find_symbol(hunk, addr, False)
        if symbol == None:
            symbol = self.find_ext_def(hunk, addr)
        if symbol == None:
            symbol = self.find_index_def(hunk, addr)
        if symbol == None and always:
            return "%08x" % addr
        return symbol

    # ----- show disassembly -----

    def show_disassembly(self, hunk, seg_list, start):
        main = hunk[0]
        lines = self.disasm.disassemble_block(main["data"], start)
        # show line by line
        for l in lines:
            addr = l[0]
            word = l[1]
            code = l[2]

            # try to find a symbol for this addr
            symbol = self.find_symbol_or_def(hunk, addr, False)

            # create line info
            info = []

            # find source line info
            line = self.find_src_line(hunk, addr)
            if line != None:
                (src_file, src_line) = line
                info.append("src: %s:%d" % (src_file, src_line))

            # find an extref
            ext_ref = self.find_ext_ref(hunk, addr, word)
            if ext_ref != None:
                ref_symbol = ext_ref[2]
                ref_type = ext_ref[3]
                info.append("%s: %s" % (ref_type, ref_symbol))

            # find a relocation
            reloc = self.find_reloc(hunk, addr, word)
            if reloc != None:
                hunk_num = reloc[2]
                offset = reloc[3]
                reloc_type_name = reloc[4]
                # a self reference
                reloc_symbol = self.find_symbol_or_def(seg_list[hunk_num], offset, True)
                if hunk_num == main["hunk_no"]:
                    src = "self"
                else:
                    src = "#%03d %s" % (hunk_num, seg_list[hunk_num][0]["type_name"])
                info.append("%s: %s: %s" % (reloc_type_name, src, reloc_symbol))

            # build comment from all infos
            if len(info) > 0:
                comment = "; " + ", ".join(info)
            else:
                comment = ""

            # create final line
            if symbol != None:
                print("\t\t\t\t%s:" % symbol)
            print(
                "%08x\t%-20s\t%-30s %s"
                % (addr, " ".join(["%04x" % x for x in word]), code, comment)
            )
