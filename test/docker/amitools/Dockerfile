FROM debian:stable AS builder

RUN apt-get update && \
  apt-get install -y git gcc python3 python3-dev python3-venv python3-pip

# create venv
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# update tools
RUN pip3 install --upgrade pip setuptools cython

RUN git clone https://github.com/cnvogelg/machine68k.git
RUN cd machine68k && pip3 install .
RUN git clone https://github.com/cnvogelg/amitools.git
RUN cd amitools && pip3 install .

# runtime
FROM debian:stable

RUN apt-get update && \
  apt-get install -y make python3

ENV PATH="/venv/bin:$PATH"
COPY --from=builder /venv /venv
