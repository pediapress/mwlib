# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""mw-render -- installed via setuptools' entry_points"""

from gevent import monkey
monkey.patch_all(thread=False)

import os
import sys
import errno
import pkg_resources
from mwlib.options import OptionParser
from mwlib import utils, wiki, conf

class Main(object):
    zip_filename = None
    
    def parse_options(self):
        parser = OptionParser()
        a = parser.add_option
        
        a("-o", "--output", help="write output to OUTPUT")
        
        a("-w", "--writer", help='use writer backend WRITER')
        
        a("-W", "--writer-options",
          help='";"-separated list of additional writer-specific options')
        
        a("-e", "--error-file", help='write errors to this file')
        
        a("-s", "--status-file",
          help='write status/progress info to this file')
        
        a("--list-writers", action='store_true',
          help='list available writers and exit')
        
        a("--writer-info", metavar='WRITER',
          help='list information about given WRITER and exit')
        
        a('--keep-zip', metavar='FILENAME',
            help='write ZIP file to FILENAME')
        
        a('--keep-tmpfiles', action='store_true', default=False,
            help="don't remove  temporary files like images")
        
        a('-L', '--language',
            help='use translated strings in LANGUAGE')
        
        options, args = parser.parse_args()
        return options, args, parser
    
    def load_writer(self, name):
        try:
            entry_point = pkg_resources.iter_entry_points('mwlib.writers', name).next()
        except StopIteration:
            sys.exit('No such writer: %r (use --list-writers to list available writers)' % name)
        try:
            return entry_point.load()
        except Exception, e:
            sys.exit('Could not load writer %r: %s' % (name, e))

    def list_writers(self):
        for entry_point in pkg_resources.iter_entry_points('mwlib.writers'):
            try:
                writer = entry_point.load()
                if hasattr(writer, 'description'):
                    description = writer.description
                else:
                    description = '<no description>'
            except Exception, e:
                description = '<NOT LOADABLE: %s>' % e
            print '%s\t%s' % (entry_point.name, description)

    def show_writer_info(self, name):
        writer = self.load_writer(name)
        if hasattr(writer, 'description'):
            print 'Description:\t%s' % writer.description
        if hasattr(writer, 'content_type'):
            print 'Content-Type:\t%s' % writer.content_type
        if hasattr(writer, 'file_extension'):
            print 'File extension:\t%s' % writer.file_extension
        if hasattr(writer, 'options') and writer.options:
            print 'Options (usable in a ";"-separated list for --writer-options):'
            for name, info in writer.options.items():
                param = info.get('param')
                if param:
                    print ' %s=%s:\t%s' % (name, param, info['help'])
                else:
                    print ' %s:\t%s' % (name, info['help'])

    def get_environment(self):
        from mwlib.status import Status
        from mwlib import nuwiki
        
        env = self.parser.makewiki()        
        if (isinstance(env.wiki, (nuwiki.NuWiki, nuwiki.adapt))
            or isinstance(env, wiki.MultiEnvironment)):
            self.status = Status(self.options.status_file, progress_range=(0, 100))
            return env

        from mwlib.apps.buildzip import make_zip
        self.zip_filename = make_zip(output=self.options.keep_zip, options=self.options, metabook=env.metabook, status=self.status)

        if env.images:
            try:
                env.images.clear()
            except OSError, err:
                if err.errno!=errno.ENOENT:
                    raise
                
        env = wiki.makewiki(self.zip_filename)
        self.status = Status(self.options.status_file, progress_range=(34, 100))
        return env
            
        
    def __call__(self):    
        options, args, parser = self.parse_options()
        conf.readrc()

        self.parser = parser
        self.options = options
        
        import tempfile
        from mwlib.writerbase import WriterError
        from mwlib.status import Status

        use_help = 'Use --help for usage information.'


        if options.list_writers:
            self.list_writers()
            return

        if options.writer_info:
            self.show_writer_info(options.writer_info)
            return
        
        if options.output is None:
            parser.error('Please specify an output file with --output.\n' + use_help)

        options.output = os.path.abspath(options.output)

        if options.writer is None:
            parser.error('Please specify a writer with --writer.\n' + use_help)    

        writer = self.load_writer(options.writer)
        writer_options = {}
        if options.writer_options:
            for wopt in options.writer_options.split(';'):
                if '=' in wopt:
                    key, value = wopt.split('=', 1)
                else:
                    key, value = wopt, True
                writer_options[str(key)] = value
        if options.language:
            writer_options['lang'] = options.language
        for option in writer_options.keys():
            if option not in getattr(writer, 'options', {}):
                print 'Warning: unknown writer option %r' % option
                del writer_options[option]

        self.status = Status(options.status_file, progress_range=(1, 33))
        self.status(progress=0)

        env = None
        try:
            env = self.get_environment()
            basename = os.path.basename(options.output)
            if '.' in basename:
                ext = '.' + basename.rsplit('.', 1)[-1]
            else:
                ext = ''
            fd, tmpout = tempfile.mkstemp(dir=os.path.dirname(options.output), suffix=ext)
            os.close(fd)
            writer(env, output=tmpout, status_callback=self.status, **writer_options)
            os.rename(tmpout, options.output)
            kwargs = {}
            if hasattr(writer, 'content_type'):
                kwargs['content_type'] = writer.content_type
            if hasattr(writer, 'file_extension'):
                kwargs['file_extension'] = writer.file_extension
            self.status(status='finished', progress=100, **kwargs)
            if options.keep_zip is None and self.zip_filename is not None:
                utils.safe_unlink(self.zip_filename)
        except Exception, e:
            import traceback
            self.status(status='error')
            if options.error_file:
                fd, tmpfile = tempfile.mkstemp(dir=os.path.dirname(options.error_file))
                f = os.fdopen(fd, 'wb')
                if isinstance(e, WriterError):
                    f.write(str(e))
                else:
                    f.write('traceback\n')
                    traceback.print_exc(file=f) 
                f.write("sys.argv=%r\n" % (utils.garble_password(sys.argv),))
                f.close()
                os.rename(tmpfile, options.error_file)
            raise
        finally:
            if env is not None and env.images is not None:
                try:
                    if not options.keep_tmpfiles:
                        env.images.clear()
                except OSError, e:
                    if e.errno!=errno.ENOENT:
                        print 'ERROR: Could not remove temporary images: %s' % e, e.errno

def main():
    return Main()()
