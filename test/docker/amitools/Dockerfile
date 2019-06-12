FROM debian:8 AS builder

RUN apt-get update && \
  apt-get install -y git gcc python python-dev python-pip
RUN pip install --upgrade pip setuptools
RUN pip install cython
RUN git clone https://github.com/cnvogelg/amitools.git
RUN cd amitools && pip install .

# runtime
FROM debian:8

RUN apt-get update && \
  apt-get install -y make python

COPY --from=builder /usr/local /usr/local/
