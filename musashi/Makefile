# Makefile for musashi

CFLAGS    = -O0 -ggdb3
#CFLAGS    = -O3

GEN_INPUT = m68k_in.c

GEN_SRC = m68kopac.c m68kopdm.c m68kopnz.c m68kops.c
GEN_HDR = m68kops.h
GEN_FILES = $(GEN_SRC) $(GEN_HDR)
GEN_OBJ = $(patsubst %.c,$(BUILD_DIR)/%.o,$(GEN_SRC))

GEN_TOOL_SRC = m68kmake.c
GEN_TOOL = m68kmake

PLUGIN = emu.so

PYX = pycpu.pyx pymem.pyx pytraps.pyx emu.pyx
GEN_C = $(patsubst %.pyx,%.c,$(PYX))

DEPS = $(PYX) mem.c mem.h traps.c traps.h
PYTHON = python
#PYTHON = python-dbg

BUILD_DIR = build

all: $(PLUGIN)

$(PLUGIN): $(GEN_SRC) $(DEPS)
	$(PYTHON) setup.py build_ext -i

gen: $(GEN_TOOL) $(GEN_OBJ)

$(BUILD_DIR)/$(GEN_TOOL): $(BUILD_DIR) $(GEN_TOOL_SRC)
	$(CC) $(CFLAGS) -o $@ $(GEN_TOOL_SRC)

$(BUILD_DIR):
	mkdir $(BUILD_DIR)

$(GEN_FILES): $(BUILD_DIR)/$(GEN_TOOL) $(GEN_INPUT)
	$(BUILD_DIR)/$(GEN_TOOL)

clean: clean_gen
	rm -rf $(BUILD_DIR)
	rm -f $(PLUGIN)
	rm -f $(GEN_C)

clean_gen:
	rm -f $(GEN_FILES)

