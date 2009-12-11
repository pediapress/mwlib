#! /usr/bin/env py.test

import signal
from mwlib.parser import styleanalyzer


def test_many_styles():
    signal.alarm(2) #, signal.siginterrupt)
    signal.signal(signal.SIGALRM, signal.default_int_handler)
    counts = [2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2]
    try:
        states = styleanalyzer.compute_path(counts)
    except KeyboardInterrupt:
        states = None
    finally:
        signal.alarm(0)

    if states is None:
        raise RuntimeError("styleanaluzer.compute_path took more then 2 seconds to finish")
