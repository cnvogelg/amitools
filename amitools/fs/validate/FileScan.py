from .BlockScan import BlockScan
from amitools.fs.FSString import FSString
from amitools.fs.FileName import FileName
from amitools.fs.validate.Log import Log
import amitools.fs.DosType as DosType


class FileData:
    def __init__(self, bi):
        self.bi = bi


class FileInfo:
    def __init__(self, bi):
        self.bi = bi


class FileScan:
    def __init__(self, block_scan, log, dos_type):
        self.block_scan = block_scan
        self.log = log
        self.dos_type = dos_type
        self.ffs = DosType.is_ffs(self.dos_type)
        self.infos = []

    def scan_all_files(self, all_file_hdr_block_infos, progress=None):
        """scan through all files"""
        if progress != None:
            progress.begin("file")
            for bi in all_file_hdr_block_infos:
                self.scan_file(bi)
                progress.add()
            progress.end()
        else:
            for bi in all_file_hdr_block_infos:
                self.scan_file(bi)

    def scan_file(self, bi):
        """scan a file header block info and create a FileInfo instance"""
        fi = FileInfo(bi)
        self.infos.append(fi)

        info = "'%s' (@%d)" % (bi.name, bi.blk_num)

        # scan for data blocks
        linked_data_blocks = bi.data_blocks
        blk_num = bi.blk_num
        # run through file list blocks linked by extension
        sbi = bi
        aborted = False
        num = 0
        while sbi.extension != 0 and sbi.extension < self.block_scan.blkdev.num_blocks:
            # check usage of block
            if self.block_scan.is_block_available(sbi.extension):
                self.log.msg(
                    Log.ERROR,
                    "File ext block #%d of %s already used" % (num, info),
                    sbi.extension,
                )
                aborted = True
                break
            # get block
            ebi = self.block_scan.get_block(sbi.extension)
            if ebi == None:
                aborted = True
                break
            # check block type
            if ebi.blk_type != BlockScan.BT_FILE_LIST:
                self.log.msg(
                    Log.ERROR,
                    "File ext block #%d of %s is no ext block" % (num, info),
                    ebi.blk_num,
                )
                aborted = True
                break
            # check for parent link
            if ebi.parent_blk != blk_num:
                self.log.msg(
                    Log.ERROR,
                    "File ext block #%d of %s has invalid parent: got %d != expect %d"
                    % (num, info, ebi.parent_blk, blk_num),
                    ebi.blk_num,
                )
            # warn if data blocks is not full
            ndb = len(ebi.data_blocks)
            if ebi.extension != 0 and ndb != self.block_scan.blkdev.block_longs - 56:
                self.log.msg(
                    Log.WARN,
                    "File ext block #%d of %s has incomplete data refs: got %d"
                    % (num, info, ndb),
                    ebi.blk_num,
                )
            # add data blocks
            linked_data_blocks += ebi.data_blocks
            sbi = ebi
            num += 1

        # transform the data block numbers to file data
        file_datas = []
        seq_num = 1
        for data_blk in linked_data_blocks:
            # get block
            block_used = self.block_scan.is_block_available(data_blk)
            dbi = self.block_scan.get_block(data_blk)
            fd = FileData(dbi)
            file_datas.append(fd)
            # check usage of block
            # is block available
            if dbi == None:
                self.log.msg(
                    Log.ERROR,
                    "File data block #%d of %s not found" % (seq_num, info),
                    data_blk,
                )
            if block_used:
                self.log.msg(
                    Log.ERROR,
                    "File data block #%d of %s already used" % (seq_num, info),
                    data_blk,
                )
                fd.bi = None
            # in ofs check data blocks
            if not self.ffs:
                # check block type
                if dbi.blk_type != BlockScan.BT_FILE_DATA:
                    self.log.msg(
                        Log.ERROR,
                        "File data block #%d of %s is no data block" % (seq_num, info),
                        data_blk,
                    )
                    fd.bi = None
                else:
                    # check header ref: must point to file header
                    if dbi.hdr_key != blk_num:
                        self.log.msg(
                            Log.ERROR,
                            "File data block #%d of %s does not ref header: got %d != expect %d"
                            % (seq_num, info, dbi.hdr_key, blk_num),
                            data_blk,
                        )
                    # check sequence number
                    if dbi.seq_num != seq_num:
                        self.log.msg(
                            Log.ERROR,
                            "File data block #%d of %s seq num mismatch: got %d"
                            % (seq_num, info, dbi.seq_num),
                            data_blk,
                        )
            seq_num += 1

        # check size of file in bytes
        block_data_bytes = self.block_scan.blkdev.block_bytes
        if not self.ffs:
            block_data_bytes -= 24
        file_est_blocks = (bi.byte_size + block_data_bytes - 1) // block_data_bytes
        num_data_blocks = len(linked_data_blocks)
        if file_est_blocks != num_data_blocks:
            self.log.msg(
                Log.ERROR,
                "File %s with %d bytes has wrong number of data blocks: got %d != expect %d"
                % (info, bi.byte_size, num_data_blocks, file_est_blocks),
                bi.blk_num,
            )

        return fi

    def dump(self):
        pass
