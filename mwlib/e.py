#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementation of mediawiki's #expr template using pyparsing's operatorPrecedence
http://meta.wikimedia.org/wiki/ParserFunctions#.23expr:
"""
import sys
import re
from pyparsing import (ParseException, Word, Literal, CaselessLiteral, 
                       Combine, Optional, nums, StringEnd,
                       operatorPrecedence, opAssoc, ParserElement)
ParserElement.enablePackrat()
if sys.version_info>=(2,6):
    ParserElement.__hash__ = lambda self: hash(id(self))

def as_float_or_int(s):
    if "." in s or "e" in s.lower():
        return float(s)
    return long(s)

# define grammar 
point = Literal('.')
number=integer = Word(nums) 
floatnumber = Combine( (integer +
                       Optional( point + Optional(number) ) +
                       Optional(  CaselessLiteral('e') + integer )) 
                       | (point + Optional(number) + Optional(  CaselessLiteral('e') + integer ))
                     ).setParseAction(lambda t: as_float_or_int(t[0]))

operand = floatnumber 

plus  = Literal("+")
minus = Literal("-")
mult  = Literal("*")
div   = Literal("/") | CaselessLiteral("div") | CaselessLiteral("mod")
addop  = plus | minus
multop = mult | div

cmpop = Literal("<>") | Literal("!=") | Literal("=") | Literal("<=") | Literal(">=") | Literal(">") | Literal("<")

expr = operatorPrecedence(operand, [
        (Literal("+") | Literal("-") | CaselessLiteral("not"), 1, opAssoc.RIGHT),
        (multop, 2, opAssoc.LEFT),
        (addop, 2, opAssoc.LEFT),
        (Literal("round"), 2, opAssoc.LEFT),
        (cmpop, 2, opAssoc.LEFT),
        (CaselessLiteral("and"), 2, opAssoc.LEFT),
        (CaselessLiteral("or"), 2, opAssoc.LEFT),
        ]) + StringEnd()

def _myround(a,b):
    r=round(a, int(b))
    if int(r)==r:
        return int(r)
    return r

binops = { "+" :    lambda a, b: a+b ,
           "-" :    lambda a, b: a-b,
           "*" :    lambda a, b: a*b,
           "/" :    lambda a, b: a/b,
           "div" :  lambda a, b: a/b,
           "mod" :  lambda a, b: int(a)%int(b),
           #               "^" :    lambda a, b: a ** b,
           "<=":    lambda a, b: int(a<=b),
           ">=":    lambda a, b: int(a>=b),
           "<":     lambda a, b: int(a<b),
           ">":     lambda a, b: int(a>b),
           "=":     lambda a, b: int(a==b),
           "<>":    lambda a, b: int(a!=b),
           "!=":    lambda a, b: int(a!=b),
           "and":   lambda a, b: int(bool(a) and bool(b)),
           "or":    lambda a, b: int(bool(a) or bool(b)),
           "round": _myround,
           }

unaops = {"not": lambda a: int(not bool(a)),
          "-": lambda a: -a,
          "+": lambda a: a,
          }

def evalExpr(r):
    #print "EVAL:", r
    if isinstance(r, (int, long, float)):
        return r
    
    lr = len(r)
    if lr==1:
        return evalExpr(r[0])
    if lr==2:
        return unaops[r[0]](evalExpr(r[1]))

    val = evalExpr(r[0])
    for opind in range(1, lr, 2):
        val = binops[r[opind]](val, evalExpr(r[opind+1]))
    return val
    
def evalString(s):
    return evalExpr(expr.parseString(s))
    
def main():
    import time
    try:
        import readline  # do not remove. makes raw_input use readline
        readline
    except ImportError:
        pass

    ep = expr
  
    while 1:
        input_string = raw_input("> ")
        if not input_string:
            continue
    
        stime = time.time()
        try:
            res=ep.parseString(input_string)
        except ParseException, err:
            print "ERROR:", err
            continue
        print res
        print time.time()-stime, "s"
        print "R:", evalExpr(res)
        

if __name__ == '__main__':
    main()
