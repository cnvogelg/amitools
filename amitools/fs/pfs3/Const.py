"""Constants of the PFS3 on-disk format (see pfs3disk.h of pfs3aio)"""

# disk types: on disk only PFS\1 and PFS\2 are valid. PFS\3 is the DosType
# that partitions for pfs3aio usually carry in their DosEnvec, PDS\3 the one
# of partitions for its direct SCSI variant
ID_PFS1 = 0x50465301
ID_PFS2 = 0x50465302
ID_PFS3 = 0x50465303
ID_PDS3 = 0x50445303
DISK_TYPES = (ID_PFS1, ID_PFS2)
# DosTypes that select PFS3 when formatting
PFS_DOS_TYPES = (ID_PFS1, ID_PFS2, ID_PFS3, ID_PDS3)

# root block option flags
MODE_HARDDISK = 0x0001
MODE_SPLITTED_ANODES = 0x0002
MODE_DIR_EXTENSION = 0x0004
MODE_DELDIR = 0x0008
MODE_SIZEFIELD = 0x0010
MODE_EXTENSION = 0x0020
MODE_DATESTAMP = 0x0040
MODE_SUPERINDEX = 0x0080
MODE_SUPERDELDIR = 0x0100
MODE_EXTROVING = 0x0200
MODE_LONGFN = 0x0400
MODE_LARGEFILE = 0x0800
MODE_STORED_GEOM = 0x1000
MODE_KNOWN = 0x1FFF

# reserved block ids
ID_EX = 0x4558
ID_MI = 0x4D49
ID_BM = 0x424D
ID_SB = 0x5342
ID_IB = 0x4942
ID_AB = 0x4142
ID_DB = 0x4442
ID_DD = 0x4444

BLOCK_ID_NAMES = {
    ID_EX: "EX",
    ID_MI: "MI",
    ID_BM: "BM",
    ID_SB: "SB",
    ID_IB: "IB",
    ID_AB: "AB",
    ID_DB: "DB",
    ID_DD: "DD",
}

# fixed locations
BOOTBLOCK1 = 0
ROOTBLOCK = 2

# anodes
ANODE_EOF = 0
ANODE_BADBLOCKS = 4
ANODE_ROOTDIR = 5
ANODE_USERFIRST = 6
RESERVEDANODES = 6
ANODE_EMPTY_BLOCKNR = 0xFFFFFFFF
MAX_ANODE_SEQNR = 0xFFFF

# index limits
MAXSMALLBITMAPINDEX = 4
MAXBITMAPINDEX = 103
MAXSMALLINDEXNR = 98
MAXSUPER = 15

# reserved area
MAXNUMRESERVED = 2093056
MAXRBLKCLUSTER = 521

# disk size limits in physical sectors
MAXSMALLDISK = 10241440
MAXDISKSIZE1K = 213021952
MAXDISKSIZE2K = 862221568
MAXDISKSIZE = 3469243648

# names
DNSIZE = 32
FNSIZE = 108
CMSIZE = 80
# the longest name a volume holds: fnsize - 1, with fnsize in [32, 107]
DEFAULT_FNSIZE = 32
MAX_FNSIZE = 107
# the handler writes no longer comment
MAX_COMMENT = 79
MAX_VOLNAME = 30

# directory entries
DIRENTRY_HEADER = 0x12
MAX_ENTRYSIZE = 254

# object types
ST_ROOT = 1
ST_USERDIR = 2
ST_SOFTLINK = 3
ST_LINKDIR = 4
ST_FILE = -3
ST_LINKFILE = -4
ST_PIPEFILE = -5
ST_ROLLOVERFILE = -16
VALID_TYPES = (
    ST_USERDIR,
    ST_SOFTLINK,
    ST_LINKDIR,
    ST_FILE,
    ST_LINKFILE,
    ST_ROLLOVERFILE,
)

TYPE_NAMES = {
    ST_USERDIR: "dir",
    ST_SOFTLINK: "softlink",
    ST_LINKDIR: "dirlink",
    ST_FILE: "file",
    ST_LINKFILE: "filelink",
    ST_ROLLOVERFILE: "rollover",
}

# extra fields: word index of each field
EXTRA_LINK_HI = 0
EXTRA_LINK_LO = 1
EXTRA_UID = 2
EXTRA_GID = 3
EXTRA_PROT_HI = 4
EXTRA_PROT_LO = 5
EXTRA_VSIZE_HI = 6
EXTRA_VSIZE_LO = 7
EXTRA_ROLL_HI = 8
EXTRA_ROLL_LO = 9
EXTRA_FSIZEX = 10
EXTRA_NUM = 11
EXTRA_MASK = 0x07FF

# deldir
DELENTRIES_PER_BLOCK = 31
DELENTRY_SIZE = 32
MAXDELDIR = 31
DELENTRY_PROT = 0x0005
DELDIR_NAME = b".DELDIR"

# postponed operations
PP_NONE = 0
PP_FREEBLOCKS_FREE = 1
PP_FREEBLOCKS_KEEP = 2
PP_FREEANODECHAIN = 3

# file size limits
MAX_FILE_SIZE = 0xFFFFFFFF
MAX_LARGE_FILE_SIZE = 0x7FFFFFFFFF

# handler version written to the root block extension by the formatter:
# the layout follows pfs3aio 20.0
PFS2VERSION = (20 << 16) | 0


def is_pfs_dos_type(dos_type):
    """is dos_type one that selects PFS3?"""
    return dos_type in PFS_DOS_TYPES
