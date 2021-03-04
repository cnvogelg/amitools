"""ELF Format Constants"""

ELFCLASS32 = 1
ELFDATA2MSB = 2
ELFOSABI_SYSV = 0
ELFOSABI_AROS = 15

EM_68K = 4

ET_values = {0: "NONE", 1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}

SHN_UNDEF = 0
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_RELA = 4
SHT_NOBITS = 8

SHT_values = {
    0: "NULL",
    1: "PROGBITS",
    2: "SYMTAB",
    3: "STRTAB",
    4: "RELA",
    5: "HASH",
    6: "DYNAMIC",
    7: "NOTE",
    8: "NOBITS",
    9: "REL",
    10: "SHLIB",
    11: "DYNSYM",
    14: "INIT_ARRAY",
    15: "FINI_ARRAY",
    16: "PREINIT_ARRAY",
    17: "GROUP",
    18: "SYMTAB_SHNDX",
}

SHT_flags = {
    1: "WRITE",
    2: "ALLOC",
    4: "EXECINSTR",
    8: "MERGE",
    16: "STRINGS",
    32: "INFO_LINK",
    64: "LINK_ORDER",
    128: "OS_NONCONFORMING",
    256: "GROUP",
    512: "TLS",
}

SHN_values = {0: "UND", 0xFFF1: "ABS"}

STB_values = {0: "LOCAL", 1: "GLOBAL", 2: "WEAK", 3: "NUM"}

STT_values = {
    0: "NOTYPE",
    1: "OBJECT",
    2: "FUNC",
    3: "SECTION",
    4: "FILE",
    5: "COMMON",
    6: "TLS",
    7: "NUM",
}

STV_values = {0: "DEFAULT", 1: "INTERNAL", 2: "HIDDEN", 3: "PROTECTED"}

R_68K_values = {0: "68K_NONE", 1: "68K_32", 4: "68K_PC32"}
