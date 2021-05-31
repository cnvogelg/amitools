# amibuild.make
#
# build programs with the following compilers:
# VBCC, GCC, AROS_GCC, SASC

SOURCES_C = exec_semaphore.c exec_copymem.c
SOURCES_C += exec_makefuncs.c exec_initstruct.c
SOURCES_C += exec_makelib.c exec_libfuncs.c
SOURCES_C += exec_initres.c exec_rawdofmt.c
SOURCES_C += dos_readargs.c dos_readargs2.c dos_findarg.c
SOURCES_C += dos_loadseg.c dos_runcmd.c
SOURCES_C += dos_system.c dos_match.c
SOURCES_C += dos_program.c dos_seek.c dos_examine.c
SOURCES_C += vprintf.c dos_stdout.c
SOURCES_C += util_muldiv.c util_date.c
SOURCES_C += math_double.c math_double_trans.c
SOURCES_C += math_single.c math_single_trans.c
SOURCES_C += math_fast.c math_fast_trans.c
SOURCES_C += test_hello.c test_raise.c
SOURCES_C += test_devtimer.c test_execpy.c
SOURCES_C += lib_testnix.c lib_testsc.c
SOURCES_C += proc_args.c

# compile a single source only?
ifdef ONLY_SOURCE
SOURCES_C := $(filter $(ONLY_SOURCE), $(SOURCES_C))
endif
export ONLY_SOURCE

LIB_GCC_SOURCES_C = testnix.c
LIB_SC_SOURCES_C = testsc.c
LIB_SRC_DIR = libs

VPATH = src

# directories
BUILD_DIR ?= bin
LIB_BUILD_DIR = $(BUILD_DIR)/libs
LIB_POSTFIXES = gcc gcc-dbg gcc-res gcc-res-dbg
LIB_POSTFIXES += sc sc-dbg sc-res sc-res-dbg
LIB_BUILD_DIRS = $(LIB_BUILD_DIR) $(patsubst %,$(LIB_BUILD_DIR)-%,$(LIB_POSTFIXES))

# external data
SASC_INSTALL_DIR ?= volumes/sc
export SASC_INSTALL_DIR

# compilers
VBCC_EXE = vc
GCC = m68k-amigaos-gcc
AROS_GCC = m68k-aros-gcc
AROS_ELF2HUNK = elf2hunk
VAMOS = ../bin/vamos
SASC = $(VAMOS) -c sasc.vamosrc sc
SLINK = $(VAMOS) -c sasc.vamosrc slink

# options
VBCC_OPTS = +aos68k -Iinclude -Indk_include/include_h
GCC_OPTS  = -noixemul -Iinclude -Werror
GCC_OPTS_LIB = -ramiga-lib -fbaserel
GCC_OPTS_LIB_RES = -ramiga-libr -resident
AROS_GCC_OPTS = -Iinclude
SASC_OPTS = SMALLDATA SMALLCODE NOSTKCHK NOCHKABORT NOICONS STRICT ANSI \
            INCDIR=include
SLINK_OPTS = SD NOICONS LIBVERSION 1 LIBREVISION 0 LIBPREFIX _LIB \
             LIB lib:sc.lib FROM lib:libent.o
SLINK_OPTS_DEF = $(SLINK_OPTS) lib:libinit.o
SLINK_OPTS_RES = $(SLINK_OPTS) lib:libinitr.o

# optimize options
VBCC_OPTI = -O2
GCC_OPTI = -O2
AROS_GCC_OPTI = -O2
SASC_OPTI = PARAMETERS=REGISTERS OPT OPTTIME OPTINLINE DEBUG=F \
            OPTSCHEDULE STRINGMERGE STRUCTUREEQUIVALENCE

# debug options
VBCC_DEBUG = -g
GCC_DEBUG = -g
AROS_GCC_DEBUG = -g
SASC_DEBUG = DEBUG=F

# libs
VBCC_LIBS = -lamiga

# binary extensions
VBCC_EXT = _vc
GCC_EXT = _gcc
AROS_GCC_EXT = _agcc
SASC_EXT = _sc
DBG_EXT = _dbg

# source to program mapping
PROGS_VBCC = $(patsubst %.c,$(BUILD_DIR)/%$(VBCC_EXT),$(SOURCES_C))
PROGS_GCC  = $(patsubst %.c,$(BUILD_DIR)/%$(GCC_EXT),$(SOURCES_C))
PROGS_AROS = $(patsubst %.c,$(BUILD_DIR)/%$(AROS_GCC_EXT),$(SOURCES_C))
PROGS_SASC = $(patsubst %.c,$(BUILD_DIR)/%$(SASC_EXT),$(SOURCES_C))

PROGS = $(PROGS_VBCC) $(PROGS_GCC) $(PROGS_AROS) $(PROGS_SASC)

PROGS_VBCC_DBG = $(patsubst %.c,$(BUILD_DIR)/%$(VBCC_EXT)$(DBG_EXT),$(SOURCES_C))
PROGS_GCC_DBG  = $(patsubst %.c,$(BUILD_DIR)/%$(GCC_EXT)$(DBG_EXT),$(SOURCES_C))
PROGS_AROS_DBG = $(patsubst %.c,$(BUILD_DIR)/%$(AROS_GCC_EXT)$(DBG_EXT),$(SOURCES_C))
PROGS_SASC_DBG = $(patsubst %.c,$(BUILD_DIR)/%$(SASC_EXT)$(DBG_EXT),$(SOURCES_C))

PROGS_DBG = $(PROGS_VBCC_DBG) $(PROGS_GCC_DBG) $(PROGS_AROS_DBG) $(PROGS_SASC_DBG)

# libraries: gcc
LIBS_GCC = $(patsubst %.c,$(LIB_BUILD_DIR)-gcc/%.library,$(LIB_GCC_SOURCES_C))
LIBS_GCC += $(patsubst %.c,$(LIB_BUILD_DIR)-gcc-res/%.library,$(LIB_GCC_SOURCES_C))
LIBS = $(LIBS_GCC)

LIBS_GCC_DBG  = $(patsubst %.c,$(LIB_BUILD_DIR)-gcc-dbg/%.library,$(LIB_GCC_SOURCES_C))
LIBS_GCC_DBG += $(patsubst %.c,$(LIB_BUILD_DIR)-gcc-res-dbg/%.library,$(LIB_GCC_SOURCES_C))
LIBS_DBG = $(LIBS_GCC_DBG)

# libraries: sc
LIBS_SC  = $(patsubst %.c,$(LIB_BUILD_DIR)-sc/%.library,$(LIB_SC_SOURCES_C))
LIBS_SC += $(patsubst %.c,$(LIB_BUILD_DIR)-sc-res/%.library,$(LIB_SC_SOURCES_C))
LIBS += $(LIBS_SC)

LIBS_SC_DBG  = $(patsubst %.c,$(LIB_BUILD_DIR)-sc-dbg/%.library,$(LIB_SC_SOURCES_C))
LIBS_SC_DBG += $(patsubst %.c,$(LIB_BUILD_DIR)-sc-res-dbg/%.library,$(LIB_SC_SOURCES_C))
LIBS_DBG += $(LIBS_SC_DBG)

# --- rules ---

test:
	./vamos-test --auto-build

rebuild: clean build

build: check $(PROGS) $(PROGS_DBG) $(LIBS) $(LIBS_DBG)

gcc: $(PROGS_GCC) $(PROGS_GCC_DBG) $(LIBS_GCC) $(LIBS_GCC_DBG)

vbcc: $(PROGS_VBCC) $(PROGS_VBCC_DBG)

aros: $(PROGS_AROS) $(PROGS_AROS_DBG)

sasc: $(PROGS_SASC) $(PROGS_SASC_DBG) $(LIBS_SC) $(LIBS_SC_DBG)

build-docker: check gcc-docker aros-docker vbcc-docker sasc-docker

gcc-docker:
	docker/drun amiga-gcc6 /usr/bin/make gcc ONLY_SOURCE=$(ONLY_SOURCE)

aros-docker:
	docker/drun m68k-aros /usr/bin/make aros ONLY_SOURCE=$(ONLY_SOURCE)

vbcc-docker:
	docker/drun amiga-vbcc /usr/bin/make vbcc ONLY_SOURCE=$(ONLY_SOURCE)

sasc-docker:
	docker/drun --dir ../.. amitools /usr/bin/make sasc VAMOS=vamos HOME=$(PWD) ONLY_SOURCE=$(ONLY_SOURCE)

check:
	@if [ ! -d volumes/sc ]; then \
		echo "directory 'volumes/sc' is missing!" ; \
		exit 1 ; \
	fi

opt: $(PROGS)
debug: $(PROGS_DBG)

all-libs: libs libs-debug
libs: $(LIBS)
libs-debug: $(LIBS_DBG)

$(PROGS): $(BUILD_DIR)
$(LIBS): $(LIB_BUILD_DIRS)

clean:
	rm -rf $(BUILD_DIR)

# dir rules
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(LIB_BUILD_DIRS):
	mkdir -p $(LIB_BUILD_DIRS)

# rules for opt
$(BUILD_DIR)/%$(VBCC_EXT) : %.c
	$(VBCC_EXE) $(VBCC_OPTS) $(VBCC_OPTI) -o $@ $< $(VBCC_LIBS)

$(BUILD_DIR)/%$(GCC_EXT) : %.c
	$(GCC) $(GCC_OPTS) $(GCC_OPTI) -o $@ $<

$(BUILD_DIR)/%$(AROS_GCC_EXT) : %.c
	$(AROS_GCC) $(AROS_GCC_OPTS) $(AROS_GCC_OPTI) -o $@ $<

$(BUILD_DIR)/%$(SASC_EXT) : %.c
	$(SASC) $(SASC_OPTS) $(SASC_OPTI) LINK TO $@ $<
	rm -f $@.lnk $(<:.c=.o)


# rules for dbg
$(BUILD_DIR)/%$(VBCC_EXT)$(DBG_EXT) : %.c
	$(VBCC_EXE) $(VBCC_OPTS) $(VBCC_DEBUG) -o $@ $< $(VBCC_LIBS)

$(BUILD_DIR)/%$(GCC_EXT)$(DBG_EXT) : %.c
	$(GCC) $(GCC_OPTS) $(GCC_DEBUG) -o $@ $<

$(BUILD_DIR)/%$(AROS_GCC_EXT)$(DBG_EXT) : %.c
	$(AROS_GCC) $(AROS_GCC_OPTS) $(AROS_GCC_DEBUG) -o $@ $<

$(BUILD_DIR)/%$(SASC_EXT)$(DBG_EXT) : %.c
	$(SASC) $(SASC_OPTS) $(SASC_DEBUG) LINK TO $@ $<
	rm -f $@.lnk $(<:.c=.o)


# lib rules: gcc
$(LIB_BUILD_DIR)-gcc/%.library : $(LIB_SRC_DIR)/%.c
	$(GCC) $(GCC_OPTS) $(GCC_OPTI) $(GCC_OPTS_LIB) -o $@ $<

$(LIB_BUILD_DIR)-gcc-res/%.library : $(LIB_SRC_DIR)/%.c
	$(GCC) $(GCC_OPTS) $(GCC_OPTI) $(GCC_OPTS_LIB_RES) -o $@ $<

$(LIB_BUILD_DIR)-gcc-dbg/%.library : $(LIB_SRC_DIR)/%.c
	$(GCC) $(GCC_OPTS) $(GCC_DEBUG) $(GCC_OPTS_LIB) -o $@ $<

$(LIB_BUILD_DIR)-gcc-res-dbg/%.library : $(LIB_SRC_DIR)/%.c
	$(GCC) $(GCC_OPTS) $(GCC_DEBUG) $(GCC_OPTS_LIB_RES) -o $@ $<


# lib rules: sc
$(LIB_BUILD_DIR)-sc/%.o: $(LIB_SRC_DIR)/%.c
	$(SASC) libcode nostackcheck objectname=$@ $<

$(LIB_BUILD_DIR)-sc/%.library : $(LIB_BUILD_DIR)-sc/%.o
	$(SLINK) LIBFD $(FD_FILE) TO $@ $(SLINK_OPTS_DEF) $<

$(LIB_BUILD_DIR)-sc-dbg/%.o: $(LIB_SRC_DIR)/%.c
	$(SASC) libcode nostackcheck debug line objectname=$@ $<

$(LIB_BUILD_DIR)-sc-dbg/%.library : $(LIB_BUILD_DIR)-sc-dbg/%.o
	$(SLINK) LIBFD $(FD_FILE) TO $@ $(SLINK_OPTS_DEF) $<

$(LIB_BUILD_DIR)-sc-res/%.o: $(LIB_SRC_DIR)/%.c
	$(SASC) libcode nostackcheck objectname=$@ $<

$(LIB_BUILD_DIR)-sc-res/%.library : $(LIB_BUILD_DIR)-sc/%.o
	$(SLINK) LIBFD $(FD_FILE) TO $@ $(SLINK_OPTS_RES) $<

$(LIB_BUILD_DIR)-sc-res-dbg/%.o: $(LIB_SRC_DIR)/%.c
	$(SASC) libcode nostackcheck debug line objectname=$@ $<

$(LIB_BUILD_DIR)-sc-res-dbg/%.library : $(LIB_BUILD_DIR)-sc-dbg/%.o
	$(SLINK) LIBFD $(FD_FILE) TO $@ $(SLINK_OPTS_RES) $<

$(LIB_BUILD_DIR)-sc/testsc.library: FD_FILE=../amitools/data/fd/testsc_lib.fd
$(LIB_BUILD_DIR)-sc-dbg/testsc.library: FD_FILE=../amitools/data/fd/testsc_lib.fd
$(LIB_BUILD_DIR)-sc-res/testsc.library: FD_FILE=../amitools/data/fd/testsc_lib.fd
$(LIB_BUILD_DIR)-sc-res-dbg/testsc.library: FD_FILE=../amitools/data/fd/testsc_lib.fd


# special flags
$(BUILD_DIR)/math_double_sc: SASC_OPTS += Math=i
$(BUILD_DIR)/math_double_sc$(DBG_EXT): SASC_OPTS += Math=i
$(BUILD_DIR)/math_double_trans_sc: SASC_OPTS += Math=i
$(BUILD_DIR)/math_double_trans_sc$(DBG_EXT): SASC_OPTS += Math=i

$(BUILD_DIR)/math_single_sc: SASC_OPTS += Math=i
$(BUILD_DIR)/math_single_sc$(DBG_EXT): SASC_OPTS += Math=i
$(BUILD_DIR)/math_single_trans_sc: SASC_OPTS += Math=i
$(BUILD_DIR)/math_single_trans_sc$(DBG_EXT): SASC_OPTS += Math=i

$(BUILD_DIR)/math_fast_sc: SASC_OPTS += Math=f
$(BUILD_DIR)/math_fast_sc$(DBG_EXT): SASC_OPTS += Math=f
$(BUILD_DIR)/math_fast_trans_sc: SASC_OPTS += Math=f
$(BUILD_DIR)/math_fast_trans_sc$(DBG_EXT): SASC_OPTS += Math=f
