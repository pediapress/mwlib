.. _mwlib-install:

~~~~~~~~~~~~~~~~~~~~~~~
Installation of mwlib
~~~~~~~~~~~~~~~~~~~~~~~

If you're running Ubuntu 10.04 or a similar system, and you just want
to copy and paste some commands, please read :ref:`ubuntu install`

Microsoft Windows is *not* supported.

Basic Prerequisites
====================

You need to have a C compiler, a C++ compiler, make and the python
development headers installed.  mwlib will work with python 2.5, 2.6
and 2.7. It will *not* work with python versions >= 3 or < 2.5. mwlib
requires a recent UNIX-like operating system.

mwlib requires the python imaging library (pil) and the python lxml
package. In order to compile pil from source the libjpeg, zlib,
freetype and lcms header files and libraries must be present on the
system. Compiling lxml requires the libxslt and libxml2 header files
and libraries.

mwlib is split into multiple namespace packages, that each provide
different functionality:

mwlib
  core functionality; provides a parser

mwlib.rl
  generates PDF files from mediawiki articles. This is what is being
  used on wikipedia in order to generate PDF output.

mwlib.zim
  generate ZIM files from mediawiki articles


Installation of mwlib with pip/easy_install
===========================================
We recommend that you use a virtualenv for installation. If you don't
use a virtualenv for installation, the commands below must probably be
run as root.

The python imaging module must be installed. We host a patched version
that is compatible with pip/easy_install. You can install that with::

   pip install -i http://pypi.pediapress.com/simple/ pil

Make sure the output of the last command contains::

  ...
  --- JPEG support available
  --- ZLIB (PNG/ZIP) support available
  --- FREETYPE2 support available
  ...

Installation of mwlib can then be done with::

   $ pip install -i http://pypi.pediapress.com/simple/ mwlib

This will install mwlib and it's dependencies. The
"-i http://pypi.pediapress.com/simple/" command line arguments
instruct pip to use our private pypi server. It contains known "good
versions" of mwlib dependencies and bugfixes for the greenlet package.


Installation of mwlib.rl with pip/easy_install
==============================================
The following command installs the mwlib.rl package::

   pip install -i http://pypi.pediapress.com/simple/ mwlib.rl

If you want to render right-to-left texts, you must also install the
pyfribidi package::

   pip install -i http://pypi.pediapress.com/simple/ pyfribidi


.. _`test install`:

Testing the installation
============================
Use the following two commands to test the installation::

   mw-zip -c :en -o test.zip Acdc Number
   mw-render -c test.zip -o test.pdf -w rl

Open test.pdf in your PDF viewer of choice and make sure that the
result looks reasonable.

Optional Dependencies
===========================
mwlib uses a set of external programs in order to handle certain
mediawiki formats. You may have to install some or all of the
following programs depending on your needs:

- imagemagick
- texvc
- latex
- blahtexml

.. _`ubuntu install`:

Installation Instructions for Ubuntu 10.04 LTS
==============================================

The following commands can be used to install mwlib on Ubuntu 10.04
LTS. Run the following as root::

  apt-get install -y gcc g++ make python python-dev python-virtualenv	\
    libjpeg-dev libz-dev libfreetype6-dev liblcms-dev			\
    libxml2-dev libxslt-dev						\
    ocaml-nox git-core							\
    python-imaging python-lxml						\
    texlive-latex-recommended ploticus dvipng imagemagick		\
    pdftk

After that switch to a user account and run::

  virtualenv --distribute --no-site-packages ~/pp
  export PATH=~/pp/bin:$PATH
  hash -r
  export PIP_INDEX_URL=http://pypi.pediapress.com/simple/
  pip install pil
  pip install pyfribidi mwlib mwlib.rl

Install texvc::

  git clone https://github.com/pediapress/texvc
  cd texvc; make; make install PREFIX=~/pp

Then :ref:`test the installation<test install>`.


Development version
==============================
The source code is managed via git and hosted on github. Please visit
`pediapress's profile on github <https://github.com/pediapress>`_ to
get an overview of what's available and for further instruction on how
to checkout the repositories.

You will also need to install cython, re2c and gettext if you plan to
build from the git repositories.
