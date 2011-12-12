.. _mwlib-renderserver:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Running a renderserver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Overview
--------------

Running a renderserver consists in running multiple programs [#mw-serve]_.
Unless you have some special requirements, you should be able to start
a working renderserver by running the following commands::

  $ nserve.py
  $ mw-qserve
  $ nslave.py --cachedir ~/cache/
  $ postman.py

These programs have the following purposes:

nserve.py
  nserve is a HTTP server. The Collection extension is talking to that
  program directly. nserve uses at least one mw-qserve instance in
  order to distribute and manage jobs.

mw-qserve
  mw-qserve is a job queue server used to distribute and manage
  jobs. You should start one mw-qserve instance for each machine that
  is supposed to render pdf files. Unless you're operating the
  Wikipedia installation, one machine should suffice.

nslave.py
  nslave pulls new jobs from exactly one mw-qserve instance and calls
  the mw-zip and mw-render programs in order to download article
  collections and convert them to different output formats.  nslave
  uses a cache directory to store the generated documents.  nslave
  also starts an internal http server serving the content of the cache
  directory.

postman.py
  postman uploads zip collections to pediapress in case someone likes
  to order printed books. You should start one instance for each
  mw-qserve instance.


None of the programs has the ability to run as a daemon. We recommend
using `runit <http://smarden.org/runit/>`_ for process
supervision. `daemontools <http://cr.yp.to/daemontools.html>`_ is
similar solution.
Another alternative is to use `supervisor <http://supervisord.org/>`_.


.. [#mw-serve] In mwlib prior to version 0.13 it was possible to get
   away with running a single ``mw-serve`` program or even running no
   program at all by using the mwlib.cgi script. These programs have
   been removed in favor of the new tools, which provide the ability
   to scale an installation.

nserve.py usage
----------------
nserve understands the following options:

``--port=PORT``

  specify port to listen on. Default is to listen on port 8899 on any
  interface.

``--qserve=HOST:PORT``
  register qserve instance running on host HOST listening on port PORT

Any additional arguments are interpreted as additional qserve
instances to register.

The following command starts nserve listening on port 8000 using two
qserve instances::

  nserve.py --port 8000 example1:14311 example2



mw-qserve usage
---------------
mw-qserve understands the following options:

``-p PORT``
  specify port to listen on. Default is to listen on port 14311

``-i INTERFACE``
  specify interface to listen on. Default is to listen on any
  interface.



nslave.py usage
------------------
nslave understands the following options:

``--cachedir=CACHEDIR``

  specify cachedir to use. this is where nslave.py will store
  generated documents.

``--serve-files-port``
  port on which to start the http server (default is 8898)

``--url=URL``
  specify url under which the cache directory is being served. The
  default is to compute this value dynamically.

``--numprocs=NUMPROCS``
  allow up to NUMPROCS parallel jobs to be executed


postman.py usage
-------------------
postman understands the following options:

``--cachedir=CACHDIR``
  specify cachedir to use. use the same value as specified when
  calling nslave.py
