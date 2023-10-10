def show(node, indent=0, out=None):
    import sys

    if out is None:
        out = sys.stdout

    out.write(f"{node}\n")

class Node(tuple):
    def __eq__(self, other):
        return type(self) == type(other) and tuple.__eq__(self, other)

    def __ne__(self, other):
        return type(self) != type(other) or tuple.__ne__(self, other)

    def __repr__(self):
        return f"{self.__class__.__name__}{tuple.__repr__(self)}"

    def show(self, out=None):
        show(self, out=out)

    def flatten(self, expander, variables, res):
        from mwlib.templ.evaluate import flatten

        for x in self:
            if isinstance(x, str):
                res.append(x)
            else:
                flatten(x, expander, variables, res)