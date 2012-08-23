from BlockScan import BlockScan
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
    self.file_infos = None
  
  def scan(self):
    """scan through all files"""    
    # first scan all file header blocks and their linked contents
    files = self.block_scan.get_blocks_of_type(BlockScan.BT_FILE_HDR)
    file_infos = []
    for f in files:
      fi = self.scan_file(f)
      file_infos.append(fi)
    self.file_infos = file_infos
  
  def scan_file(self, bi):
    fi = FileInfo(bi)
    
    # scan for data blocks
    linked_data_blocks = bi.data_blocks
    blk_num = bi.blk_num
    # run through file list blocks linked by extension
    sbi = bi
    aborted = False
    while sbi.extension != 0 and sbi.extension < self.block_scan.blkdev.num_blocks:
      ebi = self.block_scan.get_block(sbi.extension)
      if ebi == None:
        aborted = True
        break
      # check block type
      if ebi.blk_type != BlockScan.BT_FILE_LIST:
        self.log.msg(Log.ERROR, "File ext block links to non ext block: %d" % ebi.blk_num, sbi.blk_num)
        aborted = True
        break
      # check for parent link
      if ebi.parent_blk != blk_num:
        self.log.msg(Log.ERROR, "File ext block has invalid parent: got %d != expect %d" % (ebi.parent_blk, blk_num), ebi.blk_num)
      # warn if data blocks is not full
      ndb = len(ebi.data_blocks)
      if ebi.extension != 0 and ndb != self.block_scan.blkdev.block_longs - 56:
        self.log.msg(Log.WARN, "Inside file ext block is not completely filled: got %d" % ndb, ebi.blk_num)
      # add data blocks
      linked_data_blocks += ebi.data_blocks
      sbi = ebi
    
    # transform the data block numbers to file data
    file_datas = []
    if not self.ffs:
      # in ofs check data blocks
      seq_num = 1
      for data_blk in linked_data_blocks:
        dbi = self.block_scan.get_block(data_blk)
        fd = FileData(dbi)
        file_datas.append(fd)
        # is block available
        if dbi == None:
          self.log.msg(Log.ERROR, "File data block not found", data_blk)
        # check block type
        elif dbi.blk_type != BlockScan.BT_FILE_DATA:
          self.log.msg(Log.ERROR, "File data block is no data", data_blk)
          fd.bi = None
        else:
          # check header ref: must point to file header
          if dbi.hdr_key != blk_num:
            self.log.msg(Log.ERROR, "File data does not ref header: got %d != expect %d" % (dbi.hdr_key, blk_num), data_blk)          
          # check sequence number
          if dbi.seq_num != seq_num:
            self.log.msg(Log.ERROR, "File data seq num mismatch: got %d != expect %d" % (dbi.seq_num, seq_num), data_blk)
          seq_num += 1
    
    return fi
  
  def dump(self):
    pass
    