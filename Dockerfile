FROM ubuntu:trusty
RUN apt-get update && apt-get upgrade -y
RUN apt-get \
  -o Acquire::BrokenProxy="true" \
  -o Acquire::http::No-Cache="true" \
  -o Acquire::http::Pipeline-Depth="0" \
  install -y sudo

RUN apt-get \
  -o Acquire::BrokenProxy="true" \
  -o Acquire::http::No-Cache="true" \
  -o Acquire::http::Pipeline-Depth="0" \
  install -y \
  gcc g++ make python python-dev python-virtualenv                    \
  libjpeg-dev libz-dev libfreetype6-dev liblcms-dev                   \
  libxml2-dev libxslt-dev                                             \
  ocaml-nox git-core                                                  \
  python-imaging python-lxml                                          \
  texlive-latex-recommended ploticus dvipng imagemagick               \
  pdftk

RUN pip install -i http://pypi.pediapress.com/simple/ mwlib mwlib.rl
RUN useradd -m mwuser && echo "mwuser:mwuser" | chpasswd && adduser mwuser sudo
RUN mkdir -p /data/mwcache && chown -R mwuser:mwuser /data/ && chown -R mwuser:mwuser /opt/mwlib
USER mwuser
WORKDIR /home/mwuser

CMD nserve & mw-qserve & nslave --cachedir /data/mwcache