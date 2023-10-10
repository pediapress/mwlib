# nserve/nslave only monkeypatch when imported as __main__ so, we
# monkeypatch here and then call into the respective main function
from gevent import monkey

from mwlib.core.nserve import main as nserve_main_func
from mwlib.core.nslave import main as nslave_main_func
from mwlib.networking.net.postman import main as postman_main_func

monkey.patch_all()


def nserve_main():
    return nserve_main_func()


def nslave_main():
    return nslave_main_func()


def postman_main():
    return postman_main_func()
