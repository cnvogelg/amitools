# AmigaOS library header generation helper

BASE?=vamostest
LIBTYPE?=VamosTestBase
ARCH=m68k

# the tools
FD2PRAGMA=fd2pragma
SFDC=sfdc

# the source file
FD=../../amitools/data/fd/$(BASE)_lib.fd
CLIB=clib/$(BASE)_protos.h

# derived files with fd2pragma
VC_INLINE=inline/$(BASE)_protos.h
GCC_INLINE=inline/$(BASE).h
AGCC_DEFINE=defines/$(BASE).h
PROTO=proto/$(BASE).h
PRAGMA=pragma/$(BASE).h
SFD=sfd/$(BASE)_lib.sfd

FD_OPTS=-a $(ARCH) -i $(FD) -c $(CLIB) -l $(LIBTYPE)

FILES=$(VC_INLINE) $(GCC_INLINE) $(AGCC_DEFINE) $(PROTO) $(PRAGMA) $(SFD)

all:
	$(MAKE) lib BASE=vamostest LIBTYPE=VamosTestBase
	$(MAKE) lib BASE=testnix LIBTYPE=Library

clean:
	$(MAKE) clean-lib BASE=vamostest LIBTYPE=VamosTestBase
	$(MAKE) clean-lib BASE=testnix LIBTYPE=Library

lib: $(FILES)

clean-lib:
	rm -f $(FILES)

$(SFD): $(FD)
	$(FD2PRAGMA) $(FD_OPTS) -s 112 -t sfd

$(VC_INLINE): $(FD)
	$(FD2PRAGMA) $(FD_OPTS) -s 70 -t inline

$(GCC_INLINE): $(FD)
	$(FD2PRAGMA) $(FD_OPTS) -s 47 -t inline

$(AGCC_DEFINE): $(SFD)
	$(SFDC) --target=m68k-aros --mode=macros $(SFD) -o $@

$(PROTO): $(FD)
	$(FD2PRAGMA) $(FD_OPTS) -s 38 -t proto

$(PRAGMA): $(FD)
	$(FD2PRAGMA) $(FD_OPTS) -s 6 -t pragma
