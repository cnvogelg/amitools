# amibuild.make
#
# build programs with the following compilers:
# VBCC, GCC, AROS_GCC, SASC

SOURCES_C = vprintf.c

VPATH = src

# directories
BUILD_DIR ?= bin

# external data
SASC_INSTALL_DIR ?= $(HOME)/amiga/shared/sc

# compilers
VBCC = vc
GCC = m68k-amigaos-gcc
AROS_GCC = m68k-aros-gcc
AROS_ELF2HUNK = elf2hunk
SASC = ../vamos -c sasc.vamosrc sc

# options
VBCC_OPTS = -O2
GCC_OPTS  = -O2 -noixemul
AROS_GCC_OPTS = -O2
SASC_OPTS = SMALLDATA SMALLCODE NOSTKCHK NOCHKABORT NOICONS STRICT ANSI

# binary extensions
VBCC_EXT = _vc
GCC_EXT = _gcc
AROS_GCC_EXT = _agcc
SASC_EXT = _sc

# source to program mapping
PROGS_VBCC = $(patsubst %.c,$(BUILD_DIR)/%$(VBCC_EXT),$(SOURCES_C))
PROGS_GCC  = $(patsubst %.c,$(BUILD_DIR)/%$(GCC_EXT),$(SOURCES_C))
PROGS_AROS = $(patsubst %.c,$(BUILD_DIR)/%$(AROS_GCC_EXT),$(SOURCES_C))
PROGS_SASC = $(patsubst %.c,$(BUILD_DIR)/%$(SASC_EXT),$(SOURCES_C))

PROGS = $(PROGS_VBCC) $(PROGS_GCC) $(PROGS_AROS) $(PROGS_SASC)

# --- rules ---

all: $(PROGS)

$(PROGS): $(BUILD_DIR)

clean:
	rm -rf $(BUILD_DIR)

# dir rules
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# rules
$(BUILD_DIR)/%$(VBCC_EXT) : %.c
	$(VBCC) $(VBCC_OPTS) -o $@ $<

$(BUILD_DIR)/%$(GCC_EXT) : %.c
	$(GCC) $(GCC_OPTS) -o $@ $<

$(BUILD_DIR)/%$(AROS_GCC_EXT).elf : %.c
	$(AROS_GCC) $(AROS_GCC_OPTS) -o $@ $<

$(BUILD_DIR)/%$(AROS_GCC_EXT) : $(BUILD_DIR)/%$(AROS_GCC_EXT).elf
	$(AROS_ELF2HUNK) $< $@

$(BUILD_DIR)/%$(SASC_EXT) : %.c
	$(SASC) $(SASC_OPTS) LINK TO $@ $<
