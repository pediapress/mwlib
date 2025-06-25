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
development headers installed. mwlib now works with Python 3.11 and 3.12.
It requires a recent UNIX-like operating system.

mwlib requires the Python imaging library (Pillow) and the Python lxml
package. In order to compile Pillow from source the libjpeg, zlib,
freetype and lcms header files and libraries must be present on the
system. Compiling lxml requires the libxslt and libxml2 header files
and libraries.

You will also need uv, a fast Python package installer that serves as an
alternative to pip. See :ref:`installing uv` for installation instructions.

mwlib is split into multiple namespace packages, that each provide
different functionality:

mwlib
  core functionality; provides a parser

mwlib.rl
  generates PDF files from mediawiki articles. This is what is being
  used on wikipedia in order to generate PDF output.

mwlib.zim
  generate ZIM files from mediawiki articles


.. _installing uv:

Installing uv
===========================================
uv is a fast Python package installer that serves as an alternative to pip.
You can install uv using one of the following methods:

Using a shell script (Unix-like systems)::

   $ curl -LsSf https://astral.sh/uv/install.sh | sh

Using pip::

   $ pip install uv

For more information, visit `uv's official documentation <https://github.com/astral-sh/uv>`_.

Installation of mwlib with uv
===========================================
We recommend that you use a virtualenv for installation. If you don't
use a virtualenv for installation, the commands below must probably be
run as root.

Installation of mwlib can be done with::

   $ uv pip install mwlib

Make sure the output of the last command contains::

  ...
  --- JPEG support available
  --- ZLIB (PNG/ZIP) support available
  --- FREETYPE2 support available
  ...

This will install mwlib and its dependencies.

Alternatively, if you've cloned the mwlib repository, you can install it using::

   $ make install

This will use uv to install all required dependencies.

Installation of mwlib.rl with uv
==============================================
The following command installs the mwlib.rl package::

   $ uv pip install mwlib.rl

If you want to render right-to-left texts, you must also install the
pyfribidi package::

   $ uv pip install pyfribidi


.. _`test install`:

Testing the installation
============================
Use the following two commands to test the installation::

   mw-zip -c :en -o test.zip Acdc Number
   mw-render -c test.zip -o test.pdf -w rl

Open test.pdf in your PDF viewer of choice and make sure that the
result looks reasonable.

If you've cloned the repository, you can also run the tests using::

   $ make test

This will install the development dependencies and run the test suite.

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

Installation Instructions for Modern Ubuntu/Debian Systems
==============================================

The following commands can be used to install mwlib on modern Ubuntu/Debian
systems. Run the following as root::

  apt-get install -y gcc g++ make python3 python3-dev python3-venv \
    libjpeg-dev libz-dev libfreetype6-dev liblcms2-dev \
    libxml2-dev libxslt-dev \
    re2c git \
    python3-pillow python3-lxml \
    texlive-latex-recommended ploticus dvipng imagemagick \
    pdftk

After that switch to a user account and run::

  python3 -m venv ~/pp
  export PATH=~/pp/bin:$PATH
  hash -r
  pip install uv
  uv pip install pyfribidi mwlib mwlib.rl

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

To build the C extensions and install mwlib in development mode::

   $ make build
   $ make develop

This will compile the Cython modules, generate the _uscan.cc file, and install
the package in development mode, allowing you to make changes to the code
without reinstalling.
