# nserve/nslave only monkeypatch when imported as __main__ so, we
# monkeypatch here and then call into the respective main function


from gevent import monkey
monkey.patch_all()


def nserve_main():
    from mwlib.nserve import main
    return main()


def nslave_main():
    from mwlib.nslave import main
    return main()


def postman_main():
    from mwlib.postman import main
    return main()
