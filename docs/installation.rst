~~~~~~~~~~~~~~
Installation
~~~~~~~~~~~~~~

Basic Prerequisites
====================

You need to have a C compiler, a C++ compiler, make and the python
development headers installed.  mwlib will work with python 2.5, 2.6
and 2.7. It will *not* work with python versions >= 3 or < 2.5. mwlib
requires a recent UNIX-like operating system.

Microsoft Windows is *not* supported.

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
run as root. Installation of mwlib can be done with::

   $ pip install -i http://pypi.pediapress.com/simple/ mwlib

This will install mwlib and it's dependencies. The
"-i http://pypi.pediapress.com/simple/" command line arguments
instruct pip to use our private pypi server. It contains known "good
versions" of mwlib dependencies and bugfixes for the greenlet package.

The python imaging module must also be installed. We host a patched
version that is compatible with pip/easy_install. You can install that
with::

   $ pip install -i http://pypi.pediapress.com/simple/ pil

or use the version that comes with your operating system.

Installation of mwlib.rl with pip/easy_install
==============================================
The following command installs the mwlib.rl package::

   $ pip install -i http://pypi.pediapress.com/simple/ mwlib.rl

If you want to render right-to-left texts, you must also install the
pyfribidi package::

   $ pip install -i http://pypi.pediapress.com/simple/ pyfribidi


Testing the installation
============================
Use the following two commands to test the installation::

   $ mw-zip -c :en -o test.zip Acdc Number
   $ mw-render -c test.zip -o test.pdf -w rl

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
