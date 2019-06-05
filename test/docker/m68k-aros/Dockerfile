FROM debian:8 AS builder

RUN apt-get update && \
  apt-get install -y build-essential netpbm git automake make bison flex \
    python python-mako libpng12-dev wget texinfo
RUN git clone https://github.com/aros-development-team/AROS.git
RUN mkdir -p /opt/m68k-aros
RUN cd opt/m68k-aros && /AROS/configure --target=amiga-m68k && make

FROM debian:8

RUN apt-get update && \
  apt-get install -y make

ENV PATH=/opt/m68k-aros/bin/linux-x86_64/tools/crosstools/:$PATH

COPY --from=builder /opt/m68k-aros/ /opt/m68k-aros/
