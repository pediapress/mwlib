_scale = dict(kB=1024.0,  KB=1024.0,
              mB=1024.0 * 1024.0, MB=1024.0 * 1024.0)

# convert byte o MB
for k, v in _scale.items():
    _scale[k] = v / (1024.0 * 1024.0)


def _readproc(key):
    '''Private.
    '''
    try:
        v = open("/proc/self/status").read()
         # get key line e.g. 'VmRSS:  9999  kB\n ...'
        i = v.index(key)
        v = v[i:].split(None, 3)  # whitespace
        if len(v) < 3:
            return 0.0  # invalid format?
         # convert Vm value to bytes
        return float(v[1]) * _scale[v[2]]
    except:
        return 0.0  # non-Linux?


def memory():
    '''Return memory usage in MB.
    '''
    return _readproc('VmSize:')


def resident():
    '''Return resident memory usage in MB.
    '''
    return _readproc('VmRSS:')


def stacksize():
    '''Return stack size in MB.
    '''
    return _readproc('VmStk:')


def report():
    print "memory used: res=%.1f virt=%.1f" % (resident(), memory())


if __name__ == "__main__":
    report()
