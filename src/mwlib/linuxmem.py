

_scale = {"kB": 1024.0,
          "KB": 1024.0, "mB": 1024.0 * 1024.0, "MB": 1024.0 * 1024.0}

# convert byte o MB
for k, v in _scale.items():
    _scale[k] = v / (1024.0 * 1024.0)


def _readproc(key):
    """Private."""
    try:
        with open("/proc/self/status", encoding="utf-8") as proc_file:
            value = proc_file.read()
        # get key line e.g. 'VmRSS:  9999  kB\n ...'
        i = value.index(key)
        value = value[i:].split(None, 3)  # whitespace
        if len(value) < 3:
            return 0.0  # invalid format?
        # convert Vm value to bytes
        return float(value[1]) * _scale[value[2]]
    except BaseException:
        return 0.0  # non-Linux?


def memory():
    """Return memory usage in MB."""
    return _readproc("VmSize:")


def resident():
    """Return resident memory usage in MB."""
    return _readproc("VmRSS:")


def stacksize():
    """Return stack size in MB."""
    return _readproc("VmStk:")


def report():
    print(f"memory used: res={resident():.1f} virt={memory():.1f}")


if __name__ == "__main__":
    report()
