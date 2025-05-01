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
    required_args = {}

    for spec_part in spec.split():
        if spec_part.endswith("="):
            required_args[spec_part[:-1]] = True
        else:
            required_args[spec_part] = False

    opts = []
    new_args = []

    i = 0
    while i < len(args):
        arg, value = (args[i].split("=", 1) + [None])[:2]
        if arg in required_args:
            i = _process_command_line_argument(value, i, required_args, arg, args, opts)
        else:
            new_args.append(args[i])

        i += 1

    return opts, new_args
