FROM debian:stable AS builder

RUN apt-get update && \
  apt-get install -y build-essential netpbm git automake make bison flex \
    python3 python3-mako libpng-dev wget texinfo autoconf automake libtool curl \
    unzip
RUN mkdir -p /opt/m68k-aros
RUN git clone https://github.com/aros-development-team/AROS.git && \
  cd AROS && git submodule init && git submodule update

# fix config.guess for osx-arm64
RUN cp /usr/share/misc/config.guess /AROS/tools/MetaMake/

WORKDIR /opt/m68k-aros

# configure
RUN /AROS/configure --target=amiga-m68k

# build cross compiler
RUN make tools-crosstools

# build all
RUN make

RUN mv bin/linux-* bin/linux

# now build final image
FROM debian:stable

RUN apt-get update && \
  apt-get install -y make

ENV PATH=/opt/m68k-aros/bin/linux/tools/crosstools/:$PATH

COPY --from=builder /opt/m68k-aros/bin/linux/tools/crosstools/ /opt/m68k-aros/bin/linux/tools/crosstools/
COPY --from=builder /opt/m68k-aros/bin/amiga-m68k/AROS/Developer/ /opt/m68k-aros/bin/amiga-m68k/AROS/Developer/

WORKDIR /opt/m68k-aros
ARG TARGETPLATFORM
RUN case "${TARGETPLATFORM}" in \
         "linux/amd64")  ARCH=arm64  ;; \
         "linux/arm64")  ARCH=aarch64  ;; \
         *) exit 1 ;; \
    esac; \
    ln -s linux bin/linux-$ARCH
