.. -*- mode: rst; coding: utf-8 -*-

Writers
=============

A *writer* in mwlib generates output from a collection of MediaWiki articles
in some writer-specific format.

The writer function
-------------------

Essentially a writer is just a Python function with the following signature::

    def writer(env, output, status_callback, **kwargs): pass

Note that the function doesn't necessarily have to be called "writer".

The ``env`` argument is an ``mwlib.wiki.Environment`` instance which always has
the ``wiki`` attribute set to the configured ``WikiDB`` instance and the
``metabook`` attribute set to a filled-in ``mwlib.metabook.MetaBook`` instance.
If images are used, the ``images`` attribute of the ``env`` object is set to
the configure ``ImageDB`` instance.

The ``output`` argument is a filename of a file in which the writer should
write its output.

The ``status_callback`` argument is a callable with the following signature::

    def status_callback(status=None, progress=None, article=None): pass

which should be called from time to time to update the status/progress
information. ``status`` should be set to a short, English description of
what's happening (e.g. "parsing", "rendering"), ``progress`` should be an
integer value between 0 and 100 indicating the percentage of progress
(actually you don't have to worry about setting it to 0 at the start and to
100 at the end, this is done by ``mw-render``) and ``article`` should
be the unicode string of the currently processed article. All parameters
are optional, so you can pass only one or two of the parameters to
``status_callback()`` and the other parameters will keep their previous
value.

The return value of the writer function is not used: If the function returns,
this is treated as success. To indicate failure, the writer must raise an
exception. Use the ``WriterError`` exception defined in ``mwlib.writerbase``
(or a subclass thereof) and instantiate it with a human readable
English error message if you want the message to be written to the error
file specified with the ``--error-file`` option of ``mw-render``. For all
other exceptions, the traceback is written to the error file.

Your writer function can define additional keyword arguments (indicated by
the "``**kwargs``" above) that can be passed to the writer with the
``--writer-options`` argument of the ``mw-render`` command (see below).
If the user specified a writer option with ``option=value``, the kwarg
``option`` gets passed the string ``"value"``, if she specified a writer
option just with ``option``, the kwarg ``option`` gets passed the value
``True``. All writer options should be optional and documented using the
options attribute on the writer object (see below).


Attributes
----------

Optionally – and preferably – this function object has the following additional
attributes::

    writer.description = 'Some short description'
    writer.content_type = 'Content-Type of the output'
    writer.file_extension = 'File extension for documents'
    writer.options = {
        'foo: {
            'help': 'help text for "switch" foo',
        },
        'bar': {
            'param': 'PARAM',
            'help': 'help text for option bar with parameter PARAM',
        }
    }

For example the writer "odf" (defined in ``mwlib.odfwriter``) sets the
attributes to these values::

    writer.description = 'OpenDocument Text'
    writer.content_type = 'application/vnd.oasis.opendocument.text'
    writer.file_extension = 'odt'

and the writer "rl" from mwlib.rl (defined in ``mwlib.rl.rlwriter``) sets
the attributes to these values::

    writer.description = 'PDF documents (using ReportLab)'
    writer.content_type = 'application/pdf'
    writer.file_extension = 'pdf'
    writer.options = {
        'coverimage': {
            'param': 'FILENAME',
            'help': 'filename of an image for the cover page',
        }
    }

The description is used when the list of writers is displayed with
``mw-render --list-writers``, all information is displayed with
``mw-render --writer-info SOMEWRITER``. The content type and file extension
are written to a file, if one is specified with the ``--status-file`` argument
of ``mw-render``.

Publishing the writer
---------------------

Writers are made available as plugins using `setuptools entry points`_.
They have a name and must belong to the entry point group "mwlib.writers".
To publish writers in your distribution, add all included writers to the
entry group by passing the entry_points kwarg to the call to
``setuptools.setup()`` in your ``setup.py`` file::

    setup(
        ...
        entry_points = {
            'mwlib.writers': [
                'foo = somepackage.foo:writer',
                'bar = somepackage.barbaz:bar_writer',
                'baz = somepackage.barbaz:baz_writer',
            ],
        },
        ...
    )


Using writers
-------------

From the command line, writers can be used with the ``mw-render`` command.
Called with just the ``--list-writers`` option, ``mw-render`` lists the
available writers together with their description. A name of an available
writer can then be passed with the ``--writer`` option to produce output
with that writer. For example this will use the ODF writer (named "odf")
to produce a document in the OpenOffice Text format::

    $ mw-render --config :en --writer odf --output test.odt Test

Additional options for the writer can be specified with the
``--writer-options`` argument, whose value is a ";" separated list of
keywords or "key=value" pairs.


.. _`setuptools entry points`: http://peak.telecommunity.com/DevCenter/setuptools#dynamic-discovery-of-services-and-plugins
