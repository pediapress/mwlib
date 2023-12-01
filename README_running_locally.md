# Run mwlib locally with minimal docker-compose setup

For debugging purposes, it might be helpful to run mwlib locally. 
This is a minimal docker-compose setup to do so.

Please open a number of terminals and start the following processes:

1. nserve localhost:8090
2. mw-qserve -p 8090 -i localhost
3. nslave --cachedir ./cache --host localhost --port 8090 --url https://newtools.pediapress.com/cache --numprocs 2 -c makezip
4. nslave --cachedir ./cache --host localhost --port 8090 --url https://newtools.pediapress.com/cache --numprocs 2 -s makezip --serve-files-port 9123
5. postman --port 8090 --host localhost

Then, in a separate terminal, run the following command:
6. docker-compose -f docker-compose-only-mediawiki.yml up
