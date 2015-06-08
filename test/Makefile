# amibuild.make
#
# build programs with the following compilers:
# VBCC, GCC, AROS_GCC, SASC

SOURCES_C = locks.c

VPATH = src

# directories
BUILD_DIR ?= .
BUILD_VBCC_DIR ?= $(BUILD_DIR)/bin_vbcc
BUILD_GCC_DIR  ?= $(BUILD_DIR)/bin_gcc
BUILD_AROS_DIR ?= $(BUILD_DIR)/bin_aros
BUILD_SASC_DIR ?= $(BUILD_DIR)/bin_sasc
DIRS = $(BUILD_VBCC_DIR) $(BUILD_GCC_DIR) $(BUILD_AROS_DIR) $(BUILD_SASC_DIR)

# external data
SASC_INSTALL_DIR ?= $(HOME)/amiga/shared/sc

# compilers
VBCC = vc
GCC = m68k-amigaos-gcc
AROS_GCC = m68k-aros-gcc
AROS_ELF2HUNK = elf2hunk
SASC = ../vamos -c vamosrc sc

# options
VBCC_OPTS = -O2
GCC_OPTS  = -O2 -noixemul
AROS_GCC_OPTS = -O2
SASC_OPTS = SMALLDATA SMALLCODE NOSTKCHK NOCHKABORT NOICONS STRICT ANSI

# source to program mapping
PROGS_VBCC = $(patsubst %.c,$(BUILD_VBCC_DIR)/%,$(SOURCES_C))
PROGS_GCC  = $(patsubst %.c,$(BUILD_GCC_DIR)/%,$(SOURCES_C))
PROGS_AROS = $(patsubst %.c,$(BUILD_AROS_DIR)/%,$(SOURCES_C))
PROGS_SASC = $(patsubst %.c,$(BUILD_SASC_DIR)/%,$(SOURCES_C))

PROGS = $(PROGS_VBCC) $(PROGS_GCC) $(PROGS_AROS) $(PROGS_SASC)

# --- rules ---

all: $(DIRS) $(PROGS)

clean:
	rm -rf $(DIRS)

# dir rules
$(BUILD_VBCC_DIR):
	mkdir -p $(BUILD_VBCC_DIR)

$(BUILD_GCC_DIR):
	mkdir -p $(BUILD_GCC_DIR)

$(BUILD_AROS_DIR):
	mkdir -p $(BUILD_AROS_DIR)

$(BUILD_SASC_DIR):
	mkdir -p $(BUILD_SASC_DIR)

# rules
$(BUILD_VBCC_DIR)/% : %.c
	$(VBCC) $(VBCC_OPTS) -o $@ $<

$(BUILD_GCC_DIR)/% : %.c
	$(GCC) $(GCC_OPTS) -o $@ $<

$(BUILD_AROS_DIR)/%.elf : %.c
	$(AROS_GCC) $(AROS_GCC_OPTS) -o $@ $<

$(BUILD_AROS_DIR)/% : $(BUILD_AROS_DIR)/%.elf
	$(AROS_ELF2HUNK) $< $@

$(BUILD_SASC_DIR)/% : %.c
	$(SASC) $(SASC_OPTS) LINK TO $@ $<
