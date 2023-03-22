# Copyright (c) 2007-2021 PediaPress GmbH
# See README.md for additional licensing information.

IMAGE_LABEL ?= latest
IMAGE_NAME=mwlib

RST2HTML ?= rst2html.py

default::

install::
	pip-compile-multi
	pip install -r requirements/base.txt
	pip install -r requirements/test.txt

build:: src/mwlib/_uscan.cc cython MANIFEST.in

cython:: src/mwlib/templ/nodes.c src/mwlib/templ/evaluate.c

src/mwlib/templ/nodes.c: src/mwlib/templ/nodes.pyx
	cython -3 src/mwlib/templ/nodes.pyx

src/mwlib/templ/evaluate.c: src/mwlib/templ/evaluate.pyx
	cython -3 src/mwlib/templ/evaluate.pyx

src/mwlib/_uscan.cc: src/mwlib/_uscan.re
	re2c -w --no-generation-date -o src/mwlib/_uscan.cc src/mwlib/_uscan.re

documentation:: README.html
	cd docs; make html

MANIFEST.in::
	./make-manifest

README.html: README.rst
	$(RST2HTML) README.rst >README.html

develop:: build
	pip install -e .

clean::
	rm -rf build dist
	rm -f src/mwlib/templ/evaluate.c src/mwlib/templ/nodes.c src/mwlib/_uscan.cc
	rm -f mwlib/_gitversion.py*
	rm **/*.pyc || true
	pip uninstall -y mwlib || true
	pip freeze | xargs pip uninstall -y

sdist:: build
	echo gitversion=\"$(shell git describe --tags)\" >mwlib/_gitversion.py
	echo gitid=\"$(shell git rev-parse HEAD)\" >>mwlib/_gitversion.py

	python setup.py -q build sdist
	rm -f mwlib/_gitversion.py mwlib/_gitversion.pyc

sdist-upload:: sdist
	python setup.py build sdist upload -r pypi

pip-install:: clean sdist
	pip uninstall -y mwlib || true
	pip install dist/*

update::
	git pull
	make pip-install


test::
	pip install -r requirements/test.txt
	py.test tests

docker-py27-build::
	docker build -t ${IMAGE_NAME}-py27:${IMAGE_LABEL} -f Dockerfile-dev-py27 .

docker-py27-debug::
	docker run -it --rm ${IMAGE_NAME}-py27:${IMAGE_LABEL} bash

docker-py27-test::
	docker run -it --rm ${IMAGE_NAME}-py27:${IMAGE_LABEL} pytest
