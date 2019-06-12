CONTAINERS = m68k-aros amiga-gcc6 amiga-vbcc amitools

all:
	@for a in $(CONTAINERS) ; do \
		(cd $$a && docker build -t $$a .) ; done