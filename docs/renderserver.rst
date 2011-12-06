.. _mwlib-renderserver:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Running a renderserver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Overview
--------------

Running a renderserver requires running multiple programs [#mw-serve]_:

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
  collections and convert them to different output formats.
  nslave uses a cache directory to store the generated documents.

  You also need to start a webserver like nginx or apache serving the
  content of the cache directory for each nslave instance

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
