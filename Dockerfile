FROM debian:12

RUN apt-get update && apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev \
xz-utils tk-dev libffi-dev liblzma-dev curl git python3 python3-pip

RUN useradd -m python
USER python
WORKDIR /home/python

RUN git clone https://github.com/pyenv/pyenv.git .pyenv

ENV HOME  /home/python
ENV PYENV_ROOT $HOME/.pyenv
ENV PATH $PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH

# setup python
RUN for a in 3.8.16 3.9.16 3.10.9 3.11.4 3.12.5 ; do pyenv install $a ; done
RUN pyenv global 3.11.4 && pip install tox

# run-tox script
RUN echo '#!/bin/bash' > $HOME/run-tox ;\
    echo 'eval "$(pyenv init -)"' >> $HOME/run-tox ;\
    echo 'pyenv shell 3.12.5 3.11.4 3.10.9 3.9.16 3.8.16' >> $HOME/run-tox ;\
    echo 'exec tox --workdir $HOME -vv "$@"' >> $HOME/run-tox ;\
    chmod 755 $HOME/run-tox

WORKDIR /src
ENTRYPOINT [ "/home/python/run-tox" ]
