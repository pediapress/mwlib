# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

RST2HTML = rst2html.py

default:: subdirs

all:: subdirs documentation MANIFEST.in

documentation:: README.html
	cd docs; make all

subdirs::
	cd mwlib; make

MANIFEST.in::
	./make_manifest.py

README.html: README.txt
	$(RST2HTML) README.txt >README.html

develop:: all
	python setup.py develop

sdist:: all
	python setup.py build sdist

egg:: all
	python setup.py bdist_egg

clean::
	rm -rf mwlib/*.pyc mwlib/*.so build dist mwlib.egg-info *.pyc docs/*.html README.html
	rm -f mwlib/_mwscan.cc
