# mwlib - MediaWiki Parser and Utility Library

## Overview
**mwlib** is a versatile library designed for parsing MediaWiki articles and converting them to various output formats. A notable application of mwlib is in Wikipedia's "Print/export" feature, where it is used to create PDF documents from Wikipedia articles.


## Getting Started

### Prerequisites
To build mwlib, ensure you have the following software installed:
- Python (version 3.11 or 3.12)
- Ploticus
- re2c
- Perl
- Pillow / PyImage
- ImageMagick
- uv (Python package installer, faster alternative to pip)


Setup a virtual environment for Python 3.11 or 3.12 and activate it.

#### Installing uv
If you don't have uv installed, you can install it following the instructions at [uv's official documentation](https://github.com/astral-sh/uv).

For example, on Unix-like systems:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or using pip:
```bash
pip install uv
```

#### Installing mwlib
To install all dependencies and the project, run:

    $ make install

This will use uv to install all required dependencies.

To build the C extensions and install mwlib in development mode:

    $ make build
    $ make develop

Documentation

Please visit http://mwlib.readthedocs.org/en/latest/index.html for
detailed documentation.

## Docker Compose Setup
For users interested in setting up mwlib using Docker Compose, detailed instructions are available at [Docker Compose documentation](https://docs.docker.com/compose/).


License

Copyright (c) 2007-2012 PediaPress GmbH

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

.. _SpamBayes: http://spambayes.sourceforge.net/
