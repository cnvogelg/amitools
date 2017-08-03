# Makefile for musashi

BUILD_DIR = build
GEN_DIR = gen
DIST_DIR = dist

CFLAGS    = -O3

GEN_INPUT = musashi/m68k_in.c

GEN_SRC = m68kopdm.c m68kopnz.c m68kops.c
GEN_HDR = m68kops.h
GEN_FILES = $(GEN_SRC:%=$(GEN_DIR)/%) $(GEN_HDR:%=$(GEN_DIR)/%)

GEN_TOOL_SRC = musashi/m68kmake.c
GEN_TOOL = m68kmake

PYTHON = python
#PYTHON = python-dbg

.PHONY: all clean_gen clean_gen clean_all
.PHONY: do_gen do_build_inplace do_test do_dev do_install

do_build_inplace: do_gen
	$(PYTHON) setup.py build_ext -i

do_test: do_gen
	$(PYTHON) setup.py test

do_install: do_gen
	$(PYTHON) setup.py install

do_dev: do_gen
	$(PYTHON) setup.py develop --user

clean: clean_gen
	rm -rf $(BUILD_DIR)

clean_all: clean
	rm -rf $(DIST_DIR)

clean_git:
	git clean -fxd

do_gen: $(BUILD_DIR)/$(GEN_TOOL) $(GEN_DIR) $(GEN_FILES)

sdist: do_gen
	$(PYTHON) setup.py sdist --formats=gztar,zip

upload: sdist
	twine upload dist/*

$(BUILD_DIR)/$(GEN_TOOL): $(BUILD_DIR) $(GEN_TOOL_SRC)
	$(CC) $(CFLAGS) -o $@ $(GEN_TOOL_SRC)

$(BUILD_DIR):
	mkdir $(BUILD_DIR)

$(GEN_DIR):
	mkdir $(GEN_DIR)

$(GEN_FILES): $(BUILD_DIR)/$(GEN_TOOL) $(GEN_DIR) $(GEN_INPUT)
	$(BUILD_DIR)/$(GEN_TOOL) gen $(GEN_INPUT)

clean_gen:
	rm -rf $(GEN_DIR)

