class ArgumentError(Exception):
    pass


def _process_command_line_argument(value, i, needarg, arg, args, opts):
    if value is None and needarg[arg]:
        i += 1
        try:
            value = args[i]
        except IndexError as exc:
            raise ArgumentError(f"option {arg} needs an argument") from exc
    opts.append((arg, value))
    return i


def parse(args, spec):
    needarg = {}

    for spec_part in spec.split():
        if spec_part.endswith("="):
            needarg[spec_part[:-1]] = True
        else:
            needarg[spec_part] = False

    opts = []
    newargs = []

    i = 0
    while i < len(args):
        arg, value = (args[i].split("=", 1) + [None])[:2]
        if arg in needarg:
            i = _process_command_line_argument(value, i, needarg, arg, args, opts)
        else:
            newargs.append(args[i])

        i += 1

    return opts, newargs
