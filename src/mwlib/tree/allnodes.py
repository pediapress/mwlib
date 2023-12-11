import mwlib.parser
import mwlib.tree.advtree


def allnodes():
    all_nodes = set()
    names = set()
    for mw_object in (mwlib.parser, mwlib.tree.advtree):
        for directory in dir(mw_object):
            if directory in names:
                continue
            k = getattr(mw_object, directory)
            if isinstance(k, type) and issubclass(k, mwlib.parser.Node):
                all_nodes.add(k)
                names.add(directory)
    return all_nodes


if __name__ == "__main__":
    # EXAMPLE THAT SHOWS HOW TO IDENTIFY MISSING NODES
    from mwlib.parser import Chapter, Control

    my = {Control, Chapter}
    missing = allnodes() - my
    if len(missing) != len(allnodes()) - 2:
        raise AssertionError(f"Missing nodes: {missing}")
