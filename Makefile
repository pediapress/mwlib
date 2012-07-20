# Copyright (c) 2007-2008 PediaPress GmbH
# See README.rst for additional licensing information.

RST2HTML ?= rst2html.py

default:: 

all:: mwlib/_uscan.cc cython MANIFEST.in

cython:: mwlib/templ/nodes.c mwlib/templ/evaluate.c

mwlib/templ/nodes.c: mwlib/templ/nodes.py
	cython mwlib/templ/nodes.py

mwlib/templ/evaluate.c: mwlib/templ/evaluate.py
	cython mwlib/templ/evaluate.py

mwlib/_uscan.cc: mwlib/_uscan.re
	re2c -w --no-generation-date -o mwlib/_uscan.cc mwlib/_uscan.re

documentation:: README.html
	cd docs; make html

MANIFEST.in::
	./make-manifest

README.html: README.rst
	$(RST2HTML) README.rst >README.html

develop:: all
	python setup.py develop

clean::
	rm -rf build dist
	rm -f mwlib/templ/evaluate.c mwlib/templ/nodes.c mwlib/_uscan.cc
	rm -f mwlib/_gitversion.py*

sdist:: all
	echo gitversion=\"$(shell git describe --tags)\" >mwlib/_gitversion.py
	echo gitid=\"$(shell git rev-parse HEAD)\" >>mwlib/_gitversion.py

	python setup.py -q build sdist
	rm -f mwlib/_gitversion.py mwlib/_gitversion.pyc

sdist-upload:: sdist
	python setup.py build sdist upload

pip-install:: clean sdist
	pip uninstall -y mwlib || true
	pip install dist/*

update::
	git pull
	make pip-install
