FROM debian:10 AS builder

RUN apt-get update && \
  apt-get install -y git gcc python3 python3-dev python3-pip
RUN pip3 install --upgrade pip setuptools
RUN pip3 install cython
RUN git clone https://github.com/cnvogelg/amitools.git
RUN cd amitools && pip3 install .

# runtime
FROM debian:10

RUN apt-get update && \
  apt-get install -y make python3

COPY --from=builder /usr/local /usr/local/
