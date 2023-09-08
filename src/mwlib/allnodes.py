import mwlib.advtree
import mwlib.parser


def allnodes():
    all = set()
    names = set()
    for m in (mwlib.parser, mwlib.advtree):
        for x in dir(m):
            if x in names:
                continue
            k = getattr(m, x)
            if isinstance(k, type) and issubclass(k, mwlib.parser.Node):
                all.add(k)
                names.add(x)
    return all


if __name__ == "__main__":
    # EXAMPLE THAT SHOWS HOW TO IDENTIFY MISSING NODES
    from mwlib.parser import Chapter, Control

    my = {Control, Chapter}
    missing = allnodes() - my
    if len(missing) != len(allnodes()) - 2:
        raise AssertionError(f"Missing nodes: {missing}")
