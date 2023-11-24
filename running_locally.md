1. nserve localhost:8090
2. mw-qserve -p 8090 -i localhost
3. nslave --cachedir ./cache --host localhost --port 8090 --url https://newtools.pediapress.com/cache --numprocs 2 -c makezip
4. nslave --cachedir ./cache --host localhost --port 8090 --url https://newtools.pediapress.com/cache --numprocs 2 -s makezip --serve-files-port 9123
5. postman --port 8090 --host localhost
6. docker-compose -f docker-only-mediawiki-compose.yml up


python3 src/mwlib/core/test_nserve.py 