# follow these make commands to setup the environment

initial_setup:
	docker compose up -f docker-compose-initial-setup.yml -d

initial_setup_down:
	docker compose down -f docker-compose-initial-setup.yml

install_collection_extension:
	# if this snapshot is not available anymore,
	# check https://www.mediawiki.org/wiki/Special:ExtensionDistributor/Collection
	wget https://extdist.wmflabs.org/dist/extensions/Collection-REL1_40-d981285.tar.gz
	mkdir -p ./extensions
	tar -xzf Collection-REL1_40-d981285.tar.gz -C ./extensions
	rm Collection-REL1_40-d981285.tar.gz

add_collection_extension:
	# add the following line to LocalSettings.php
	# wfLoadExtension( 'Collection' );
	cp ./LocalSettings.php ./LocalSettings.php.bak
	echo "wfLoadExtension( 'Collection' );" >> ./LocalSettings.php
