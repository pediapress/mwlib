# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.
"""
class for defining DTD-Like Rules for the tree
"""
from advtree import Article

from mwlib.log import Log
log = Log("sanitychecker")

# -----------------------------------------------------------
# Constraints
# -----------------------------------------------------------

class ConstraintBase(object):
    def __init__(self, *klasses):
        self.klasses = klasses

    def test(self, nodes): 
        return True,None # passed

    def __repr__(self):
        return "%s(%s)" %(self.__class__.__name__, ", ".join(k.__name__ for k in self.klasses))


class Forbid(ConstraintBase):
    "forbid any of the classes"
    def test(self, nodes): 
        for n in nodes:
            if n.__class__ in self.klasses:
                return False, n
        return True, None
    

class Allow(ConstraintBase):
    "allow only these classes"
    def test(self, nodes): 
        for n in nodes:
            if not n.__class__ in self.klasses:
                return False, n
        return True, None


class Require(ConstraintBase):
    "require any of these classes"
    def test(self, nodes): 
        for n in nodes:
            if n.__class__ in self.klasses:
                return True, n
        return False, None
  
class Equal(ConstraintBase):
    "node classes and their order must be equal to these klasses"
    def test(self, nodes): 
        if len(nodes) != len(self.klasses):
            return False, None # FIXME what could we report?
        for i,n in enumerate(nodes):
            if n.__class__ !=  self.klasses[i]:
                return False, n
        return True, None
    

# -----------------------------------------------------------
# Rules regarding [Children, AllChildren, Parents, ...]
# -----------------------------------------------------------

class RuleBase:
    def __init__(self, klass, constraint):
        self.klass = klass
        self.constraint = constraint
    
    def _tocheck(self, node):
       return [] 

    def test(self, node):
        if node.__class__ == self.klass:
            return self.constraint.test( self._tocheck(node) )
        return True, None

    def __repr__(self):
        return "%s(%s, %r)" %(self.__class__.__name__, self.klass.__name__, self.constraint)

class ChildrenOf(RuleBase):
    def _tocheck(self, node):
        return node.children

class AllChildrenOf(RuleBase):
    def _tocheck(self, node):
        return node.getAllChildren()

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
        self.klass = klass

    def __repr__(self):
        return "%s(%s)" %(self.__class__.__name__, self.klass.__name__)

    def test(self, node):
        if node.__class__ == self.klass:
            if not len(node.children):
                return False, node
        return True, None




# -----------------------------------------------------------
# Callbacks
# -----------------------------------------------------------
"""
callbacks get called if added to rules
callback return values should be:
 * True if it modified the tree and the sanity check needs to restart
 * False if the tree is left unmodified
"""
class SanityException(Exception):
    pass    

def exceptioncb(rule, node=None, parentnode=None):
    raise SanityException("%r  err:%r" %(rule, node or parentnode) )

def warncb(rule, node=None, parentnode=None):
    log.warn("%r node:%r parent:%r" %(rule, node, parentnode))
    return False

def removecb(rule, node=None, parentnode=None):
    assert node and node.parent
    node.parent.removeChild(node)
    return True



# -----------------------------------------------------------
# Container for sanity rules
# -----------------------------------------------------------

class SanityChecker(object):

    def __init__(self):
        self.rules = []

    def addRule(self, rule, actioncb=exceptioncb):
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
                #if node.__class__ == Article:
                #    log.info("checking article:", node.caption.encode('utf-8'))
                for r,cb in self.rules:
                    passed, errnode = r.test(node)
                    if not passed and cb:
                        if cb(r, errnode or node):
                            modified = True
                            break
                if modified:
                    break

def demo(tree):
    "for documentation only, see tests for more demos"
    from mwlib.advtree import Table, Row, Cell, Text, ImageLink, PreFormatted

    sc = SanityChecker()
    rules = [ChildrenOf(Table, Allow(Row)),
             ChildrenOf(Row, Allow(Cell)),
             AllChildrenOf(Cell, Require(Text, ImageLink)),
             AllChildrenOf(Cell, Forbid(PreFormatted)),
             ChildrenOf(PreFormatted, Equal(Text)),
             ]
    
    def mycb(rule, node=None, parentnode=None):
        print "failed", rule, node or parentnode
        modifiedtree = False
        return modifiedtree

    for r in rules:
        sc.addRule( r, mycb)
    #sc.check(anytree)
    

