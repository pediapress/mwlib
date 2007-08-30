# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

all:: README.html MANIFEST.in

MANIFEST.in::
	./make_manifest.py

README.html: README.txt
	rst2html.py README.txt >README.html

develop:: all
	python setup.py develop

sdist:: all
	python setup.py build sdist

egg:: all
	python setup.py bdist_egg

