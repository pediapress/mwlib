import sys
import traceback

import gevent


def safe_call(fun, *args, **kwargs):
    try:
        return fun(*args, **kwargs)
    except gevent.GreenletExit:
        raise
    except Exception:
        pass


class CallInLoop:
    def __init__(self, sleep_time, function, *args, **kwargs):
        self.sleep_time = sleep_time
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        return "<call_in_loop %s %s %r %r>" % (
            self.sleep_time,
            self.function.__name__,
            self.args,
            self.kwargs,
        )

    def iterate(self):
        try:
            self.function(*self.args, **self.kwargs)
        except gevent.GreenletExit:
            raise
        except Exception:
            safe_call(self.report_error)
        safe_call(gevent.sleep, self.sleep_time)

    def __call__(self):
        while 1:
            try:
                self.iterate()
            except gevent.GreenletExit:
                raise
            except Exception:
                pass

    def report_error(self):
        exc_info = sys.exc_info()
        sys.stderr.write("\nError while calling %s:\n" % self.function)
        traceback.print_exception(*exc_info)
        sys.stderr.write("\n")
