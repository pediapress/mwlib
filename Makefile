# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

RST2HTML = rst2html.py

default:: subdirs

all:: subdirs cython documentation MANIFEST.in

cython:: mwlib/templ/nodes.c mwlib/templ/evaluate.c

mwlib/templ/nodes.c: mwlib/templ/nodes.py
	cython mwlib/templ/nodes.py

mwlib/templ/evaluate.c: mwlib/templ/evaluate.py
	cython mwlib/templ/evaluate.py

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

sdist-upload:: all
	python setup.py build sdist upload

egg:: all
	python setup.py bdist_egg

clean::
	rm -rf mwlib/*.pyc mwlib/*.so build dist mwlib.egg-info *.pyc docs/*.html README.html
	rm -f mwlib/_mwscan.cc
	rm -f mwlib/templ/*.so mwlib/templ/*.c
