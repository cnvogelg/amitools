# Makefile for musashi

OS = $(shell uname -s)
ifeq "$(OS)" "Darwin"
CC = clang
SO_EXT = dylib
else
CC = gcc
SO_EXT = so
endif
CFLAGS = -g -O2 --std=c99

BUILD_DIR = BUILD

SRC = mem.c traps.c m68kcpu.c m68kdasm.c
HDR = mem.h traps.h m68k.h m68kcpu.h m68kconf.h
OBJ = $(patsubst %.c,$(BUILD_DIR)/%.o,$(SRC))

GEN_INPUT = m68k_in.c

GEN_SRC = m68kopac.c m68kopdm.c m68kopnz.c m68kops.c
GEN_HDR = m68kops.h
GEN_FILES = $(GEN_SRC) $(GEN_HDR)
GEN_OBJ = $(patsubst %.c,$(BUILD_DIR)/%.o,$(GEN_SRC))

GEN_TOOL_SRC = m68kmake.c
GEN_TOOL_OBJ = $(patsubst %.c,$(BUILD_DIR)/%.o,$(GEN_TOOL_SRC))
GEN_TOOL = m68kmake

ALL_SRC = $(SRC) $(GEN_SRC)
ALL_OBJ = $(OBJ) $(GEN_OBJ)

LIB = libmusashi.$(SO_EXT)

all: build

build: $(BUILD_DIR) $(LIB)

$(SRC): $(GEN_HDR) $(HDR)

$(BUILD_DIR):
	mkdir $(BUILD_DIR)

gen: $(GEN_TOOL) $(GEN_OBJ)

$(GEN_TOOL): $(BUILD_DIR) $(GEN_TOOL_OBJ)
	$(CC) $(CFLAGS) -o $@ $(GEN_TOOL_OBJ)

$(GEN_FILES): $(GEN_TOOL) $(GEN_INPUT)
	./$(GEN_TOOL)

$(LIB): $(ALL_OBJ)
	$(CC) -shared -o $@ $(ALL_OBJ)

clean: clean_gen
	rm -f $(GEN_TOOL)
	rm -rf $(BUILD_DIR)
	rm -f $(LIB)

clean_gen:
	rm -f $(GEN_FILES)

$(BUILD_DIR)/%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<