# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.
"""
class for defining DTD-Like Rules for the tree
"""

import logging

from mwlib.parser.advtree import Cell, ImageLink, PreFormatted, Row, Table, Text
from mwlib.utils.mwlib_exceptions import SanityException

log = logging.getLogger("sanitychecker")

# -----------------------------------------------------------
# Constraints
# -----------------------------------------------------------


class ConstraintBase:
    def __init__(self, *klasses):
        self.klasses = klasses

    def test(self, _):
        return True, None  # passed

    def __repr__(self):
        return "{}({})".format(
            self.__class__.__name__, ", ".join(
                k.__name__ for k in self.klasses))


class Forbid(ConstraintBase):
    "forbid any of the classes"

    def test(self, nodes):
        for node in nodes:
            if node.__class__ in self.klasses:
                return False, node
        return True, None


class Allow(ConstraintBase):
    "allow only these classes"

    def test(self, nodes):
        for node in nodes:
            if node.__class__ not in self.klasses:
                return False, node
        return True, None


class Require(ConstraintBase):
    "require any of these classes"

    def test(self, nodes):
        for node in nodes:
            if node.__class__ in self.klasses:
                return True, node
        return False, None


class Equal(ConstraintBase):
    "node classes and their order must be equal to these klasses"

    def test(self, nodes):
        if len(nodes) != len(self.klasses):
            return False, None  # FIXME what could we report?
        for i, node in enumerate(nodes):
            if node.__class__ != self.klasses[i]:
                return False, node
        return True, None


# -----------------------------------------------------------
# Rules regarding [Children, AllChildren, Parents, ...]
# -----------------------------------------------------------


class RuleBase:
    def __init__(self, klass, constraint):
        self.klass = klass
        self.constraint = constraint

    def _tocheck(self, _):
        return []

    def test(self, node):
        if node.__class__ == self.klass:
            return self.constraint.test(self._tocheck(node))
        return True, None

    def __repr__(self):
        return f"{self.__class__.__name__}({self.klass.__name__}, {self.constraint!r})"


class ChildrenOf(RuleBase):
    def _tocheck(self, node):
        return node.children


class AllChildrenOf(RuleBase):
    def _tocheck(self, node):
        return node.get_all_children()


class ParentsOf(RuleBase):
    def _tocheck(self, node):
        return node.parents


class ParentOf(RuleBase):
    def _tocheck(self, node):
        if node.parent:
            return [node.parent]
        return []


class SiblingsOf(RuleBase):
    def _tocheck(self, node):
        return node.siblings


# example custom rules


class RequireChild(RuleBase):
    def __init__(self, klass):
        super().__init__(klass, Require(klass))
        self.klass = klass

    def __repr__(self):
        return f"{self.__class__.__name__}({self.klass.__name__})"

    def test(self, node):
        if node.__class__ == self.klass and not node.children:
            return False, node
        return True, None


# -----------------------------------------------------------
# Callbacks
# -----------------------------------------------------------
# callbacks get called if added to rules
# callback return values should be:
# * True if it modified the tree and the sanity check needs to restart
# * False if the tree is left unmodified


def exceptioncb(rule, node=None, parentnode=None):
    raise SanityException(f"{rule!r}  err:{node or parentnode!r}")


def warncb(rule, node=None, parentnode=None):
    log.warn(f"{rule!r} node:{node!r} parent:{parentnode!r}")
    return False


def removecb(node=None, parentnode=None):
    if not node or not node.parent:
        raise SanityException(f"cannot remove {node!r} from {parentnode!r}")
    node.parent.remove_child(node)
    return True


# -----------------------------------------------------------
# Container for sanity rules
# -----------------------------------------------------------


class SanityChecker:
    def __init__(self):
        self.rules = []

    def add_rule(self, rule, actioncb=exceptioncb):
        self.rules.append((rule, actioncb))

    def check(self, tree):
        """
        check each node with each rule
        on failure call callback
        """
        modified = True
        while modified:
            modified = False
            for node in tree.allchildren():
                for rule, callback in self.rules:
                    passed, errnode = rule.test(node)
                    if not passed and callback and callback(errnode or node):
                        modified = True
                        break
                if modified:
                    break


def demo():
    """for documentation only, see tests for more demos."""
    sanity_checker = SanityChecker()
    rules = [
        ChildrenOf(Table, Allow(Row)),
        ChildrenOf(Row, Allow(Cell)),
        AllChildrenOf(Cell, Require(Text, ImageLink)),
        AllChildrenOf(Cell, Forbid(PreFormatted)),
        ChildrenOf(PreFormatted, Equal(Text)),
    ]

    def mycb(rule, node=None, parentnode=None):
        print("failed", rule, node or parentnode)
        modifiedtree = False
        return modifiedtree

    for rule in rules:
        sanity_checker.add_rule(rule, mycb)
