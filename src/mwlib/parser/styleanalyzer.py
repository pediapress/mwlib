# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

# '''bold'''
# ''italic''


from mwlib.exceptions.mwlib_exceptions import InconsistentPathLengthException


class State:
    def __init__(self, **kw):
        self.apocount = 0
        self.is_bold = False
        self.is_italic = False
        self.__dict__.update(kw)

    def clone(self, **kw):
        state = State(**self.__dict__)
        state.__dict__.update(kw)
        return state

    def __repr__(self):
        res = ["<state ", f" {self.apocount} "]
        if self.is_bold:
            res.append("bold ")
        if self.is_italic:
            res.append("italic ")

        res.append(">")
        return "".join(res)

    def __lt__(self, other):
        # default_3way_compare from Python 2 as Python code
        # same type but no ordering defined, go by id
        self_type = type(self)
        other_type = type(other)
        if self_type is other_type:
            return id(self) < id(other)
        raise TypeError(f"unorderable types: {self_type.__name__}() < {other_type.__name__}()")

    def get_next(self, count, res=None, previous=None):
        if previous is None:
            previous = self

        if res is None:
            res = []

        def nextstate(**kw):
            cloned_state = self.clone(previous=previous, **kw)
            res.append(cloned_state)
        if count < 2:
            raise ValueError("count must be >= 2")

        if count == 2:
            nextstate(is_italic=not self.is_italic)

        if count == 3:
            nextstate(is_bold=not self.is_bold)

            state = self.clone(apocount=self.apocount + 1, previous=previous)

            state.get_next(2, res, previous=previous)

        if count == 4:
            state = self.clone(apocount=self.apocount + 1)
            state.get_next(3, res, previous=previous)

        if count == 5:
            for next_state in self.get_next(2):
                next_state.get_next(3, res, previous=previous)
            for next_state in self.get_next(3):
                next_state.get_next(2, res, previous=previous)

            state = self.clone(apocount=self.apocount)
            state.get_next(4, res, previous=previous)

        if count > 5:
            state = self.clone(apocount=self.apocount + (count - 5))
            state.get_next(5, res, previous=previous)

        return res


def sort_states(states):
    tmp = sorted([((x.apocount + x.is_bold + x.is_italic), x) for x in states])
    return [x[1] for x in tmp]


def compute_path(counts):
    states = [State(is_bold=False, is_italic=False, previous=None, apocount=0)]

    for count in counts:
        new_states = []
        for state in states:
            state.get_next(count, new_states)
        states = new_states
        states = sort_states(states)
        best = states[0]
        if best.apocount == 0 and not best.is_italic and not best.is_bold:
            states = [best]
        else:
            states = states[:32]

    tmp = states[0]

    res = []
    while tmp.previous is not None:
        res.append(tmp)
        tmp = tmp.previous

    res.reverse()

    if len(res) != len(counts):
        raise InconsistentPathLengthException(len(counts), len(res))
    return res
