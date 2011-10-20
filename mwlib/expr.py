#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.
# based on pyparsing example code (SimpleCalc.py)

"""Implementation of mediawiki's #expr template. 
http://meta.wikimedia.org/wiki/ParserFunctions#.23expr:
"""

from __future__ import division

import re
import inspect
import math

class ExprError(Exception):
    pass

def _myround(a,b):
    r=round(a, int(b))
    if int(r)==r:
        return int(r)
    return r


pattern = """
(?:\s+)
|((?:(?:\d+)(?:\.\d+)?
 |(?:\.\d+)) (?:e(?:\+|-)?\d+)?)
|(\+|-|\*|/|>=|<=|<>|!=|[a-zA-Z]+|.)
"""

rxpattern = re.compile(pattern, re.VERBOSE | re.DOTALL | re.IGNORECASE)
def tokenize(s):
    res = []
    for (v1,v2) in rxpattern.findall(s):
        if not (v1 or v2):
            continue
        v2=v2.lower()
        if v2 in Expr.constants:
            res.append((v2,""))
        else:
            res.append((v1,v2))
    return res
        
    return [(v1,v2.lower()) for (v1,v2) in rxpattern.findall(s) if v1 or v2]

class uminus: pass
class uplus: pass

precedence = {"(":-1, ")":-1}
functions = {}
unary_ops = set()

def addop(op, prec, fun, numargs=None):
    precedence[op] = prec
    if numargs is None:
        numargs = len(inspect.getargspec(fun)[0])

    if numargs==1:
        unary_ops.add(op)
    
    def wrap(stack):
        assert len(stack)>=numargs
        args = tuple(stack[-numargs:])
        del stack[-numargs:]
        stack.append(fun(*args))

    functions[op] = wrap
        
a=addop
a(uminus, 10, lambda x: -x)
a(uplus, 10, lambda x: x)
a("^", 10, math.pow, 2)
a("not", 9, lambda x:int(not(bool(x))))
a("abs", 9, abs, 1)
a("sin", 9, math.sin, 1)
a("cos", 9, math.cos, 1)
a("asin", 9, math.asin, 1)
a("acos", 9, math.acos, 1)
a("tan", 9, math.tan, 1)
a("atan", 9, math.atan, 1)
a("exp", 9, math.exp, 1)
a("ln", 9, math.log, 1)
a("ceil", 9, lambda x: int(math.ceil(x)))
a("floor", 9, lambda x: int(math.floor(x)))
a("trunc", 9, long, 1)

a("*", 8, lambda x,y: x*y)
a("/", 8, lambda x,y: x/y)
a("div", 8, lambda x,y: x/y)
a("mod", 8, lambda x,y: int(x)%int(y))


a("+", 6, lambda x,y: x+y)
a("-", 6, lambda x,y: x-y)

a("round", 5, _myround)

a("<", 4, lambda x,y: int(x<y))
a(">", 4, lambda x,y: int(x>y))
a("<=", 4, lambda x,y: int(x<=y))
a(">=", 4, lambda x,y: int(x>=y))
a("!=", 4, lambda x,y: int(x!=y))
a("<>", 4, lambda x,y: int(x!=y))
a("=", 4, lambda x,y: int(x==y))

a("and", 3, lambda x,y: int(bool(x) and bool(y)))
a("or", 2, lambda x,y: int(bool(x) or bool(y)))
del a

class Expr(object):
    constants = dict(
        e=math.e,
        pi=math.pi)
    
    def as_float_or_int(self, s):
        try:
            return self.constants[s]
        except KeyError:
            pass
        
        if "." in s or "e" in s.lower():
            return float(s)
        return long(s)
    
    def output_operator(self, op):
        return functions[op](self.operand_stack)
    
    def output_operand(self, operand):
        self.operand_stack.append(operand)
            
    def parse_expr(self, s):
        tokens = tokenize(s)
        if not tokens:
            return ""
        
        self.operand_stack = []
        operator_stack = []
        
        last_operand, last_operator = False, True
        
        for operand, operator in tokens:
            if operand:
                if last_operand:
                    raise ExprError("expected operator")
                self.output_operand(self.as_float_or_int(operand))
            elif operator=="(":
                operator_stack.append("(")
            elif operator==")":
                while 1:
                    if not operator_stack:
                        raise ExprError("unbalanced parenthesis")
                    t = operator_stack.pop()
                    if t=="(":
                        break
                    self.output_operator(t)
            elif operator in precedence:
                if last_operator and last_operator!=")":
                    if operator=='-':
                        operator = uminus
                    elif operator=='+':
                        operator = uplus
                        
                is_unary = operator in unary_ops
                prec = precedence[operator]
                while not is_unary and operator_stack and prec<=precedence[operator_stack[-1]]:
                    p = operator_stack.pop()
                    self.output_operator(p)
                operator_stack.append(operator)
            else:
                raise ExprError("unknown operator: %r" % (operator,))

            last_operand, last_operator = operand, operator
            
            
        while operator_stack:
            p=operator_stack.pop()
            if p=="(":
                raise ExprError("unbalanced parenthesis")
            self.output_operator(p)
            
        if len(self.operand_stack)!=1:
            raise ExprError("bad stack: %s" % (self.operand_stack,))

        return self.operand_stack[-1]

_cache = {}
def expr(s):
    try:
        return _cache[s]
    except KeyError:
        pass
    
    
    r = Expr().parse_expr(s)
    _cache[s] = r
    return r


def main():
    import time
    try:
        import readline  # do not remove. makes raw_input use readline
        readline
    except ImportError:
        pass
  
    while 1:
        input_string = raw_input("> ")
        if not input_string:
            continue
    
        stime = time.time()
        try:
            res=expr(input_string)
        except Exception, err:
            print "ERROR:", err
            import traceback
            traceback.print_exc()
            
            continue
        print res
        print time.time()-stime, "s"

if __name__=='__main__':
    main()
    
        
