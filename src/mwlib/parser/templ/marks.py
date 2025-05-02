
class Mark(str):
    def __new__(klass, msg):
        new_instance = str.__new__(klass)
        new_instance.msg = msg
        return new_instance

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.msg!r}>"


class MarkStart(Mark):
    pass


class MarkEnd(Mark):
    pass


class MarkMaybeNewline(Mark):
    pass


maybe_newline = MarkMaybeNewline("maybe_newline")
dummy_mark = Mark("dummy")


class _EqMark(str):
    def __eq__(self, other):
        return self is other


eqmark = _EqMark("=")
