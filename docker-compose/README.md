# Setting up a MediaWiki instance with Docker Compose

This is a simple example of how to set up a MediaWiki instance with Docker Compose. The Makefile contains a few commands to make it easier to work with the containers and set everything up correctly.

This setup is based on the docker-compose.yml file featured in the official [Mediawiki](https://registry.hub.docker.com/_/mediawiki/) docker image.

## Prerequisites
make sure you have the following installed:

* [Docker](https://docs.docker.com/engine/installation/)
* [Docker Compose](https://docs.docker.com/compose/install/)
* [OrbStack](https://github.com/orbstack/orbstack) is the fast, light, and easy way to run Docker containers and Linux machines on macOS. It's a supercharged WSL and Docker Desktop alternative, all in one easy-to-use app.

## Usage
Mediawiki requires an initial setup phase where it installs the database and creates the admin user. This is done by running the `initial_setup` command. When asked about the database host, enter `database` (the internal docker name of the database container).

```shell
make initial_setup
```
MediaWiki will be available at [http://localhost:8080](http://localhost:8080).

After that, you can shut down the containers with the following `make` command:

```shell
make initial_setup_down
``` 

Then, you can download and install the collection extension with the `install_collection_extension` command.



```shell
make install_collection_extension
```
It will modify the `LocalSettings.php` file and add the following lines:

```php
wfLoadExtension( 'Collection' );
```
## Add mediawiki to your local hosts

sudo nano /etc/hosts
127.0.0.1   mediawiki

Afterwards, the collection extension will be available at [http://mediawiki/index.php/Special:Collection](http://localhost:8080/index.php/Special:Collection).

TODO: figure out how to add the collection extension links to the sidebar.

To add extension link login and go to the index.php?title=MediaWiki:Sidebar&action=edit
and add following line special:book|Collection


## References

https://www.mediawiki.org/wiki/Special:ExtensionDistributor/Collection
https://www.mediawiki.org/wiki/Extension:Collection
