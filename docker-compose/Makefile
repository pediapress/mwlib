# follow these make commands to setup the environment

# Directory for extensions
EXTENSIONS_DIR := ./extensions
# MediaWiki Collection extension tarball URL
COLLECTION_URL := https://extdist.wmflabs.org/dist/extensions/Collection-REL1_40-29bc85d.tar.gz
# Collection tarball file name
COLLECTION_TAR := Collection-REL1_40-29bc85d.tar.gz
# LocalSettings backup file
LOCAL_SETTINGS_BAK := ./LocalSettings.php.bak
# Docker container name for MariaDB
DB_CONTAINER_NAME := database

initial_setup:
	mkdir -p $(EXTENSIONS_DIR)
	docker compose -f docker-compose-initial-setup.yml up -d
	
grant_privilges:
	docker exec $(DB_CONTAINER_NAME) mariadb -uroot -p'password' -e "GRANT ALL ON *.* TO 'wikiuser'@'%' IDENTIFIED BY 'password'; FLUSH PRIVILEGES;"

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