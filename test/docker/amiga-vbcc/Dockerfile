FROM debian:10 AS builder

RUN apt-get update && \
  apt-get install -y build-essential wget lhasa

RUN mkdir -p /opt/vbcc/bin

# vasm
RUN wget http://sun.hasenbraten.de/vasm/release/vasm.tar.gz
RUN tar xvfz vasm.tar.gz
RUN cd vasm && make CPU=m68k SYNTAX=mot vasmm68k_mot
RUN cd vasm && make vobjdump
RUN cp vasm/vasmm68k_mot /opt/vbcc/bin/
RUN cp vasm/vobjdump /opt/vbcc/bin/

# vlink
RUN wget http://sun.hasenbraten.de/vlink/release/vlink.tar.gz
RUN tar xvfz vlink.tar.gz
RUN cd vlink && make
RUN cp vlink/vlink /opt/vbcc/bin/

# vbcc
RUN wget http://server.owl.de/~frank/tags/vbcc0_9g.tar.gz
RUN tar xvfz vbcc0_9g.tar.gz
RUN mkdir vbcc/bin
RUN cd vbcc && printf 'y\ny\nsigned char\ny\nunsigned char\nn\ny\nsigned short\nn\ny\nunsigned short\nn\ny\nsigned int\nn\ny\nunsigned int\nn\ny\nsigned long long\nn\ny\nunsigned long long\nn\ny\nfloat\nn\ny\ndouble\n' | make TARGET=m68k
RUN cd vbcc && printf 'y\ny\nsigned char\ny\nunsigned char\nn\ny\nsigned short\nn\ny\nunsigned short\nn\ny\nsigned int\nn\ny\nunsigned int\nn\ny\nsigned long long\nn\ny\nunsigned long long\nn\ny\nfloat\nn\ny\ndouble\n' | make TARGET=m68ks
RUN rm vbcc/bin/dtgen
RUN cp vbcc/bin/* /opt/vbcc/bin/

# vbcc targets
RUN mkdir /opt/vbcc/targets
RUN wget http://server.owl.de/~frank/vbcc/2017-08-14/vbcc_target_m68k-amigaos.lha
RUN wget http://server.owl.de/~frank/vbcc/2017-08-14/vbcc_target_m68k-kick13.lha
RUN lha x vbcc_target_m68k-amigaos.lha
RUN lha x vbcc_target_m68k-kick13.lha
RUN cp -a vbcc_target_m68k-amigaos/targets/* /opt/vbcc/targets/
RUN cp -a vbcc_target_m68k-kick13/targets/* /opt/vbcc/targets/
RUN find /opt/vbcc/targets -type f -exec chmod 644 {} \;

# vbcc config
RUN wget http://server.owl.de/~frank/vbcc/2017-08-14/vbcc_unix_config.tar.gz
RUN tar xvfz vbcc_unix_config.tar.gz
RUN mkdir /opt/vbcc/config
RUN cp config/aos* config/kick* /opt/vbcc/config/
RUN find /opt/vbcc/config -type f -exec chmod 644 {} \;

# ndk
RUN wget http://www.haage-partner.de/download/AmigaOS/NDK39.lha
RUN lha x NDK39.lha
RUN mkdir -p /opt/vbcc/ndk/include
RUN cp -a NDK_3.9/Include/include_h/* /opt/vbcc/ndk/include/
RUN find /opt/vbcc/ndk/include -type f -exec chmod 644 {} \;
RUN cd /opt/vbcc/targets/m68k-amigaos/include && for a in /opt/vbcc/ndk/include/* ; do ln -s $a ; done
RUN cd /opt/vbcc/targets/m68k-kick13/include && for a in /opt/vbcc/ndk/include/* ; do ln -s $a ; done

# runtime
FROM debian:10

RUN apt-get update && \
  apt-get install -y make

ENV PATH=/opt/vbcc/bin:$PATH
ENV VBCC=/opt/vbcc

COPY --from=builder /opt/vbcc/ /opt/vbcc/
