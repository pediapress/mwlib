#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.
# based on pyparsing example code (SimpleCalc.py)

"""Implementation of mediawiki's #expr template. 
http://meta.wikimedia.org/wiki/ParserFunctions#.23expr:
"""

from __future__ import division

import re
from pyparsing import (ParseException, Word, Literal, CaselessLiteral, 
                       Combine, Optional, nums, Forward, ZeroOrMore, StringEnd)

def _myround(a,b):
    r=round(a, int(b))
    if int(r)==r:
        return int(r)
    return r

class ExpressionParser(object):
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

    unaops = {"not": lambda a: int(not bool(a))}

    def __init__(self):        
        self.exprStack = []

        # define grammar
        point = Literal('.')
        plusorminus = Literal('+') | Literal('-')
        number = Word(nums) 
        integer = Combine( Optional(plusorminus) + number )
        floatnumber = Combine( (integer +
                               Optional( point + Optional(number) ) +
                               Optional(  CaselessLiteral('e') + integer )) 
                               | (point + Optional(number) + Optional(  CaselessLiteral('e') + integer ))
                             )

        plus  = Literal("+")
        minus = Literal("-")
        mult  = Literal("*")
        div   = Literal("/") | CaselessLiteral("div") | CaselessLiteral("mod")
        lpar  = Literal("(").suppress()
        rpar  = Literal(")").suppress()
        addop  = plus | minus
        multop = mult | div

        cmpop = Literal("<>") | Literal("!=") | Literal("=") | Literal("<=") | Literal(">=") | Literal(">") | Literal("<")

        expr = Forward()
        atom = ( ( floatnumber | integer ).setParseAction(self._push_first) | 
                 ( lpar + expr.suppress() + rpar )
               )

        factor = Forward()
        factor << ((CaselessLiteral("not") + factor).setParseAction(self._push_first) | atom)

        term = factor + ZeroOrMore( ( multop + factor ).setParseAction( self._push_first ) )
        adds = term + ZeroOrMore( ( addop + term ).setParseAction( self._push_first ) )
        
        rounds = adds + ZeroOrMore( (CaselessLiteral("round") + adds).setParseAction(self._push_first)) 

        cmps = rounds + ZeroOrMore( (cmpop + rounds).setParseAction(self._push_first) )

        ands = cmps + ZeroOrMore( (CaselessLiteral("and")+cmps).setParseAction(self._push_first))
        ors = ands + ZeroOrMore( (CaselessLiteral("or")+ands).setParseAction(self._push_first))

        expr << ors

        self.pattern =  expr + StringEnd()

    def parse(self, s):
        self.exprStack[:] = []
        return self.pattern.parseString(s)

    def eval(self):
        return self._eval(self.exprStack[:])

    def __call__(self, s):
        self.parse(s)
        return self.eval()

    def _eval(self, s=None):
        opn = self.binops
        uop = self.unaops

        op = s.pop()
        if op in opn:
            op2 = self._eval( s )
            op1 = self._eval( s )
            return opn[op]( op1, op2 )
        elif op in uop:
            op1 = self._eval(s)
            return uop[op](op1)
        elif re.search('^[-+]?[0-9]+$',op):
            return long( op )
        else:
            return float( op )
    

    def _push_first(self, str, loc, toks ):
        self.exprStack.append(toks[0])


def main():
    try:
        import readline  # do not remove. makes raw_input use readline
    except ImportError:
        pass

    ep = ExpressionParser()
  
    while 1:
        input_string = raw_input("> ")
        if not input_string:
            continue
    
        try:
            ep.parse(input_string)
        except ParseException, err:
            print "ERROR:", err
            continue
        print ep.exprStack
        print ep.eval()


if __name__ == '__main__':
    main()
