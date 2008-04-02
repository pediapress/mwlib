#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""#expr parser using pyparsing's operatorPrecedence.
not used and not usable at the moment
"""

from pyparsing import (ParseException, Word, Literal, CaselessLiteral, 
                       Combine, Optional, nums, StringEnd, operatorPrecedence, oneOf, opAssoc)

# define grammar 
point = Literal('.')
number=integer = Word(nums) 
floatnumber = Combine( (integer +
                       Optional( point + Optional(number) ) +
                       Optional(  CaselessLiteral('e') + integer )) 
                       | (point + Optional(number) + Optional(  CaselessLiteral('e') + integer ))
                     )

operand = floatnumber | integer 

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
        

if __name__ == '__main__':
    main()
