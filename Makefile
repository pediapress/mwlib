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

build:: src/mwlib/parser/token/_uscan.cc cython MANIFEST.in

cython:: src/mwlib/parser/templ/node.c src/mwlib/parser/templ/nodes.c src/mwlib/parser/templ/evaluate.c

src/mwlib/parser/templ/node.c: src/mwlib/parser/templ
	cython -3 src/mwlib/parser/templ/node.pyx

src/mwlib/parser/templ/nodes.c: src/mwlib/parser/templ
	cython -3 src/mwlib/parser/templ/nodes.pyx

src/mwlib/parser/templ/evaluate.c: src/mwlib/parser/templ
	cython -3 src/mwlib/parser/templ/evaluate.pyx

src/mwlib/parser/token/_uscan.cc: src/mwlib/parser/token/_uscan.re
	re2c -w --no-generation-date -o src/mwlib/parser/token/_uscan.cc src/mwlib/parser/token/_uscan.re

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
	rm -f src/mwlib/templ/node.c src/mwlib/templ/evaluate.c src/mwlib/templ/nodes.c src/mwlib/_uscan.cc
	rm -f mwlib/_gitversion.py*
	rm **/*.pyc || true
	uv pip uninstall mwlib || true
	#uv pip freeze | xargs pip uninstall -y

sdist:: build
	echo gitversion=\"$(shell git describe --tags)\" > _gitversion.py
	echo gitid=\"$(shell git rev-parse HEAD)\" >> _gitversion.py

	python3 setup.py -q build sdist
	rm -f _gitversion.py _gitversion.pyc

sdist-upload:: sdist
	python3 setup.py build sdist upload -r pypi

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


# Docker compose related targets
# follow these make commands to setup the environment

# Directory for extensions
EXTENSIONS_DIR := ./mediawiki/extensions
# Collection tarball file name
COLLECTION_TAR := Collection-REL1_39-73539ac.tar.gz    
# MediaWiki Collection extension tarball URL
COLLECTION_URL := https://extdist.wmflabs.org/dist/extensions/$(COLLECTION_TAR) 
# LocalSettings backup file
LOCAL_SETTINGS_BAK := ./LocalSettings.php.bak
# Docker container name for MariaDB
DB_CONTAINER_NAME := database

initial_setup:
	mkdir -p $(EXTENSIONS_DIR)
	docker compose -f docker-compose-initial-setup.yml up -d

grant_privilges:
	docker compose exec $(DB_CONTAINER_NAME) mariadb -uroot -ppassword -e "GRANT ALL ON *.* TO 'wikiuser'@'%' IDENTIFIED BY 'password'; FLUSH PRIVILEGES;"

initial_setup_down:
	docker compose -f docker-compose-initial-setup.yml down

install_collection_extension:
	mkdir -p $(EXTENSIONS_DIR)
	wget $(COLLECTION_URL) -O $(COLLECTION_TAR)
	tar -xzf $(COLLECTION_TAR) -C $(EXTENSIONS_DIR)
	rm $(COLLECTION_TAR)

add_collection_extension:
	# add the following line to LocalSettings.php
	# wfLoadExtension( 'Collection' );
	cp ./LocalSettings.php $(LOCAL_SETTINGS_BAK)
	echo "wfLoadExtension( 'Collection' );" >> ./LocalSettings.php

run:
	docker compose up --build

down:
	docker compose down
