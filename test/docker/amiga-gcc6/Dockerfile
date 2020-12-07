FROM debian:10 AS builder

RUN apt-get update && \
  apt-get install -y build-essential python git gperf automake \
    bison flex ncurses-dev libgmp-dev libmpfr-dev libmpc-dev \
    gettext texinfo wget rsync
RUN git clone https://github.com/bebbo/amiga-gcc
RUN cd amiga-gcc && mkdir -p /opt/m68k-amiga && \
  make update && make all

FROM debian:10

RUN apt-get update && \
  apt-get install -y make libgmp10 libmpfr6 libmpc3

ENV PATH=/opt/amiga/bin:$PATH

COPY --from=builder /opt/amiga/ /opt/amiga/
