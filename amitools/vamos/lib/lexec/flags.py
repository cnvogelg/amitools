from enum import IntFlag


class MemFlag(IntFlag):
    MEMF_ANY = 0
    MEMF_PUBLIC = 1 << 0
    MEMF_CHIP = 1 << 1
    MEMF_FAST = 1 << 2
    MEMF_LOCAL = 1 << 8
    MEMF_24BITDMA = 1 << 9
    MEMF_KICK = 1 << 10

    MEMF_CLEAR = 1 << 16
    MEMF_LARGEST = 1 << 17
    MEMF_REVERSE = 1 << 18
    MEMF_TOTAL = 1 << 19

    MEMF_NO_EXPUNGE = 1 << 31
