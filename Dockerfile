FROM debian:11

RUN apt-get update && apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev \
xz-utils tk-dev libffi-dev liblzma-dev curl git python3 python3-pip

RUN pip3 install tox tox-pyenv

RUN useradd -m python
USER python
WORKDIR /home/python

RUN git clone git://github.com/pyenv/pyenv.git .pyenv

ENV HOME  /home/python
ENV PYENV_ROOT $HOME/.pyenv
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH

# setup python
RUN for a in 3.6.15 3.7.12 3.8.12 3.9.9 3.10.1 ; do pyenv install $a ; done

# run-tox script
RUN echo '#!/bin/sh' > $HOME/run-tox ;\
    echo 'eval "$(pyenv init -)"' >> $HOME/run-tox ;\
    echo 'pyenv shell 3.10.1 3.9.9 3.8.12 3.7.12 3.6.15' >> $HOME/run-tox ;\
    echo 'exec tox "$@"' >> $HOME/run-tox ;\
    chmod 755 $HOME/run-tox

WORKDIR /src
ENTRYPOINT [ "/home/python/run-tox" ]
