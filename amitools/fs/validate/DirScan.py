from .BlockScan import BlockScan
from amitools.fs.FSString import FSString
from amitools.fs.FileName import FileName
from amitools.fs.validate.Log import Log
import amitools.fs.DosType as DosType


class DirChainEntry:
    """entry of the hash chain"""

    def __init__(self, blk_info):
        self.blk_info = blk_info
        self.parent_ok = False
        self.fn_hash_ok = False
        self.valid = False
        self.end = False
        self.orphaned = False
        self.sub = None

    def __str__(self):
        l = []
        if self.parent_ok:
            l.append("parent_ok")
        if self.fn_hash_ok:
            l.append("fn_hash_ok")
        if self.valid:
            l.append("valid")
        if self.end:
            l.append("end")
        if self.orphaned:
            l.append("orphaned")
        return "[DCE @%d '%s': %s]" % (
            self.blk_info.blk_num,
            self.blk_info.name,
            " ".join(l),
        )


class DirChain:
    """representing a chain of the hashtable in a directory"""

    def __init__(self, hash_val):
        self.hash_val = hash_val
        self.chain = []

    def add(self, dce):
        self.chain.append(dce)

    def get_entries(self):
        return self.chain

    def __str__(self):
        return "{DirChain +%d: #%d}" % (self.hash_val, len(self.chain))


class DirInfo:
    """information structure on a directory"""

    def __init__(self, blk_info):
        self.blk_info = blk_info
        self.chains = {}
        self.children = []

    def add(self, dc):
        self.chains[dc.hash_val] = dc

    def add_child(self, c):
        self.children.append(c)

    def get(self, hash_val):
        if hash_val in self.chains:
            return self.chains[hash_val]
        else:
            return None

    def get_chains(self):
        return self.chains

    def __str__(self):
        bi = self.blk_info
        blk_num = bi.blk_num
        name = bi.name
        parent_blk = bi.parent_blk
        return "<DirInfo @%d '%s' #%d parent:%d child:#%d>" % (
            blk_num,
            name,
            len(self.chains),
            parent_blk,
            len(self.children),
        )


class DirScan:
    """directory tree scanner"""

    def __init__(self, block_scan, log):
        self.log = log
        self.block_scan = block_scan
        self.root_di = None
        self.intl = DosType.is_intl(block_scan.dos_type)
        self.files = []
        self.dirs = []

    def scan_tree(self, root_blk_num, progress=None):
        """scan the root tree"""
        # get root block info
        root_bi = self.block_scan.get_block(root_blk_num)
        if root_bi == None:
            self.log.msg(Log.ERROR, "Root block not found?!", root_blk_num)
            return None
        # do tree scan
        if progress != None:
            progress.begin("dir")
        self.root_di = self.scan_dir(root_bi, progress)
        if progress != None:
            progress.end()
        return self.root_di

    def scan_dir(self, dir_bi, progress):
        """check a directory by scanning through the hash table entries and follow the chains
        Returns (all_chains_ok, dir_obj)
        """
        # create new dir info
        di = DirInfo(dir_bi)
        self.dirs.append(di)

        # run through hash_table of directory and build chains
        chains = {}
        hash_val = 0
        for blk_num in dir_bi.hash_table:
            if blk_num != 0:
                # build chain
                chain = DirChain(hash_val)
                self.build_chain(chain, dir_bi, blk_num, progress)
                di.add(chain)
            hash_val += 1

        return di

    def build_chain(self, chain, dir_blk_info, blk_num, progress):
        """build a block chain"""
        dir_blk_num = dir_blk_info.blk_num
        dir_name = dir_blk_info.name
        hash_val = chain.hash_val

        # make sure entry block is first used
        block_used = self.block_scan.is_block_available(blk_num)

        # get entry block
        blk_info = self.block_scan.read_block(blk_num)

        # create dir chain entry
        dce = DirChainEntry(blk_info)
        chain.add(dce)

        # account
        if progress != None:
            progress.add()

        # block already used?
        if block_used:
            self.log.msg(
                Log.ERROR,
                "dir block already used in chain #%d of dir '%s (%d)"
                % (hash_val, dir_name, dir_blk_num),
                blk_num,
            )
            dce.end = True
            return

        # self reference?
        if blk_num == dir_blk_num:
            self.log.msg(
                Log.ERROR,
                "dir block in its own chain #%d of dir '%s' (%d)"
                % (hash_val, dir_name, dir_blk_num),
                blk_num,
            )
            dce.end = True
            return

        # not a block in range
        if blk_info == None:
            self.log.msg(
                Log.ERROR,
                "out-of-range block terminates chain #%d of dir '%s' (%d)"
                % (hash_val, dir_name, dir_blk_num),
                blk_num,
            )
            dce.end = True
            return

        # check type of entry block
        b_type = blk_info.blk_type
        if b_type not in (BlockScan.BT_DIR, BlockScan.BT_FILE_HDR):
            self.log.msg(
                Log.ERROR,
                "invalid block terminates chain #%d of dir '%s' (%d)"
                % (hash_val, dir_name, dir_blk_num),
                blk_num,
            )
            dce.end = True
            return

        # check referenceed block type in chain
        blk_type = blk_info.blk_type
        if blk_type in (
            BlockScan.BT_ROOT,
            BlockScan.BT_FILE_LIST,
            BlockScan.BT_FILE_DATA,
        ):
            self.log.msg(
                Log.ERROR,
                "invalid block type %d terminates chain #%d of dir '%s' (%d)"
                % (blk_type, hash_val, dir_name, dir_blk_num),
                blk_num,
            )
            dce.end = True
            return

        # all following are ok
        dce.valid = True

        # check parent of block
        name = blk_info.name
        dce.parent_ok = blk_info.parent_blk == dir_blk_num
        if not dce.parent_ok:
            self.log.msg(
                Log.ERROR,
                "invalid parent in '%s' chain #%d of dir '%s' (%d)"
                % (name, hash_val, dir_name, dir_blk_num),
                blk_num,
            )

        # check name hash
        fn = FileName(name, self.intl)
        fn_hash = fn.hash()
        dce.fn_hash_ok = fn_hash == hash_val
        if not dce.fn_hash_ok:
            self.log.msg(
                Log.ERROR,
                "invalid name hash in '%s' chain #%d of dir '%s' (%d)"
                % (name, hash_val, dir_name, dir_blk_num),
                blk_num,
            )

        # recurse into dir?
        if blk_type == BlockScan.BT_DIR:
            dce.sub = self.scan_dir(blk_info, progress)
        elif blk_type == BlockScan.BT_FILE_HDR:
            self.files.append(dce)

        # check next block in chain
        next_blk = blk_info.next_blk
        if next_blk != 0:
            self.build_chain(chain, dir_blk_info, next_blk, progress)
        else:
            dce.end = True

    def get_all_file_hdr_blk_infos(self):
        """return all file chain entries"""
        result = []
        for f in self.files:
            result.append(f.blk_info)
        return result

    def get_all_dir_infos(self):
        """return all dir infos"""
        return self.dirs

    def dump(self):
        """dump whole dir info structure"""
        self.dump_dir_info(self.root_di, 0)

    def dump_dir_info(self, di, indent):
        """dump a single dir info structure and its sub dirs"""
        istr = "    " * indent
        print(istr, di)
        for hash_value in sorted(di.get_chains().keys()):
            dc = di.get(hash_value)
            print(istr, " ", dc)
            for dce in dc.get_entries():
                print(istr, "  ", dce)
                sub = dce.sub
                if sub != None and dce.blk_info.blk_type == BlockScan.BT_DIR:
                    self.dump_dir_info(sub, indent + 1)
