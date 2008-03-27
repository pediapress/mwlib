.. -*- mode: rst; coding: utf-8 -*-

======================================================================
mwlib - mediawiki parser and utility library
======================================================================


Overview
======================================================================
mwlib provides a library for parsing mediawiki_ articles.
It is currently aimed at developers, who have a need to somehow handle
mediawiki articles.

Installation
======================================================================
You need to have setuptools/easy_install installed. Installation
should be as easy as typing::
  
  $ easy_install mwlib

If you don't have setuptools installed, download the source package, 
unpack it and run::

  $ python setup.py install

(this will also install setuptools)

You will also need:

*latex*
  latex is used for rendering of mathematical formulas

*perl*
  perl is used to drive the timeline.pl script, which produces
  timeline images.

*PIL*
 PIL is the Python Imaging Library and is used for image handling
 (http://www.pythonware.com/products/pil/).

Configuration
======================================================================
See example_conf.py for an example configuration.

Contact/Further Information
======================================================================
For further information please visit our trac instance running at
http://code.pediapress.com
The current development version can also be found there.

Credits
======================================================================
mwlib/cdb.py is based on the cdb implementation from the spambayes_
project ( (C) 2002-2004 Python Software Foundation ).
The remaining parts are distributed under the BSD license:

License
======================================================================
Copyright (c) 2007, 2008 PediaPress GmbH

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

* Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above
  copyright notice, this list of conditions and the following
  disclaimer in the documentation and/or other materials provided
  with the distribution. 

* Neither the name of PediaPress GmbH nor the names of its
  contributors may be used to endorse or promote products derived
  from this software without specific prior written permission. 

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

.. _mediawiki: http://www.mediawiki.org
.. _spambayes: http://spambayes.sourceforge.net/
