class ArgumentError(Exception):
    pass


def parse(args, spec):
    needarg = {}

    for x in spec.split():
        if x.endswith("="):
            needarg[x[:-1]] = True
        else:
            needarg[x] = False

    opts = []
    newargs = []

    i = 0
    while i < len(args):
        a, v = (args[i].split("=", 1) + [None])[:2]
        if a in needarg:
            if v is None and needarg[a]:
                i += 1
                try:
                    v = args[i]
                except IndexError as exc:
                    raise ArgumentError(f"option {a} needs an argument") from exc

            opts.append((a, v))
        else:
            newargs.append(args[i])

        i += 1

    return opts, newargs
