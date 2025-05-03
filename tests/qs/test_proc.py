#! /usr/bin/env py.test

import os
import sys
import time

from qs import proc


def test_run_cmd_with_this():
    st, out = proc.run_cmd([sys.executable, "-c", "import this"])
    assert "Namespaces are one honking great idea -- let's do more of those!" in out


def test_run_cmd_timeout():
    stime = time.time()
    st, out = proc.run_cmd([sys.executable, "-c", "import time; time.sleep(10)"], 0.2)
    needed = time.time() - stime
    assert (st, out) == (9, "")
    assert needed >= 0.18
    assert needed < 0.4


def test_run_cmd_trigger_loopexit():
    proc.run_cmd(
        [sys.executable, "-uc", "import time, os, this; os.close(1); os.close(2); time.sleep(0.2)"]
    )


def test_run_cmd_exit_before_close():
    st, out = proc.run_cmd(
        [
            sys.executable,
            "-uc",
            """import os; import sys; os.spawnl(os.P_NOWAIT, sys.executable, sys.executable, "-c", "from __future__ import print_function; import time; time.sleep(0.2); print('foobar!');")""",
        ]
    )
    print(st, out)
    assert (st, out) == (0, "foobar!\n")


def test_run_cmd_execfail():
    st, out = proc.run_cmd([sys.executable + "-999"])
    print("status:", st)
    print("out:", repr(out))

    assert os.WIFEXITED(st)
    assert os.WEXITSTATUS(st) == 97

    if int(sys.version[0]) < 3:
        assert "failed to exec" in out
        assert "OSError" in out
        assert "Traceback (most recent call last)" in out


def test_run_cmd_unicode():
    # the error only shows up if sys.getfilesystemencoding() != "utf-8"
    # unset LANG to enforce that and run test in an external process
    import qs

    if sys.getfilesystemencoding().lower() != "utf-8":
        print("-----", sys.getfilesystemencoding(), "----")
        qs_location = os.path.dirname(os.path.dirname(qs.__file__))
        cmd = (
            """/usr/bin/env PYTHONOPTIMIZE= LANG= %s -c 'import sys; sys.path.insert(0, %s); from qs.proc import run_cmd; st, out = run_cmd([u"echo", "hello", unichr(900)]); print st; print out; assert(st)==0, "failed to execute echo with unicode argument"'"""
            % (sys.executable, repr(qs_location).replace("'", '"'))
        )
        err = os.system(cmd)
        assert err == 0
