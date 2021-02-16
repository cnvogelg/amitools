FROM debian:10 AS builder

RUN apt-get update && \
  apt-get install -y build-essential netpbm git automake make bison flex \
    python3 python3-mako libpng-dev wget texinfo
RUN mkdir -p /opt/
RUN git clone https://github.com/aros-development-team/AROS.git && \
  cd AROS && git submodule init && git submodule update
RUN mv AROS /opt/m68k-aros
RUN cd opt/m68k-aros && ./configure --target=amiga-m68k && make

FROM debian:10

RUN apt-get update && \
  apt-get install -y make

ENV PATH=/opt/m68k-aros/bin/linux-x86_64/tools/crosstools/:$PATH

COPY --from=builder /opt/m68k-aros/bin/linux-x86_64/tools/crosstools/ /opt/m68k-aros/bin/linux-x86_64/tools/crosstools/
COPY --from=builder /opt/m68k-aros/bin/amiga-m68k/AROS/Developer/ /opt/m68k-aros/bin/amiga-m68k/AROS/Developer/
