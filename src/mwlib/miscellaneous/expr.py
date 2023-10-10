#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.
# based on pyparsing example code (SimpleCalc.py)

"""Implementation of mediawiki's #expr template.
http://meta.wikimedia.org/wiki/ParserFunctions#.23expr:
"""

import inspect
import math
import re
import time
import traceback

try:
    import readline  # do not remove. makes raw_input use readline

    readline
except ImportError:
    pass


class ExprError(Exception):
    pass


def _myround(number_to_round, decimal_places):
    if int(decimal_places) == 0 and round(number_to_round + 1) - round(number_to_round) != 1:
        return number_to_round + abs(number_to_round) / number_to_round * 0.5  # simulate Python 2 rounding
        # via https://stackoverflow.com/questions/21839140/
        # python-3-rounding-behavior-in-python-2
    rounded_number = round(number_to_round, int(decimal_places))
    if int(rounded_number) == rounded_number:
        return int(rounded_number)
    return rounded_number


PATTERN = "\n".join(
    [
        r"(?:\s+)",
        r"|((?:(?:\d+)(?:\.\d+)?",
        r" |(?:\.\d+)))",
        r"|(\+|-|\*|/|>=|<=|<>|!=|[a-zA-Z]+|.)",
    ]
)

rx_pattern = re.compile(PATTERN, re.VERBOSE | re.DOTALL | re.IGNORECASE)


def tokenize(input_string):
    res = []
    for raw_token, processed_token in rx_pattern.findall(input_string):
        if not (raw_token or processed_token):
            continue
        processed_token = processed_token.lower()
        if processed_token in Expr.constants:
            res.append((processed_token, ""))
        else:
            res.append((raw_token, processed_token))
    return res


class UMinus:
    pass


class UPlus:
    pass


precedence = {"(": -1, ")": -1}
functions = {}
unary_ops = set()


def addop(operator, prec, fun, numargs=None):
    precedence[operator] = prec
    if numargs is None:
        numargs = len(inspect.getfullargspec(fun)[0])

    if numargs == 1:
        unary_ops.add(operator)

    def wrap(stack):
        assert len(stack) >= numargs
        args = tuple(stack[-numargs:])
        del stack[-numargs:]
        stack.append(fun(*args))

    functions[operator] = wrap


a = addop
a(UMinus, 10, lambda x: -x)
a(UPlus, 10, lambda x: x)
a("^", 10, math.pow, 2)
a("not", 9, lambda x: int(not bool(x)))
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
a("trunc", 9, int, 1)

a("e", 11, lambda x, y: x * 10**y)
a("E", 11, lambda x, y: x * 10**y)

a("*", 8, lambda x, y: x * y)
a("/", 8, lambda x, y: x / y)
a("div", 8, lambda x, y: x / y)
a("mod", 8, lambda x, y: int(x) % int(y))


a("+", 6, lambda x, y: x + y)
a("-", 6, lambda x, y: x - y)

a("round", 5, _myround)

a("<", 4, lambda x, y: int(x < y))
a(">", 4, lambda x, y: int(x > y))
a("<=", 4, lambda x, y: int(x <= y))
a(">=", 4, lambda x, y: int(x >= y))
a("!=", 4, lambda x, y: int(x != y))
a("<>", 4, lambda x, y: int(x != y))
a("=", 4, lambda x, y: int(x == y))

a("and", 3, lambda x, y: int(bool(x) and bool(y)))
a("or", 2, lambda x, y: int(bool(x) or bool(y)))
del a


class Expr:
    constants = {"e": math.e, "pi": math.pi}

    def __init__(self) -> None:
        self.operand_stack = []

    def as_float_or_int(self, number):
        try:
            return self.constants[number]
        except KeyError:
            pass

        if "." in number:
            return float(number)
        return int(number)

    def output_operator(self, operator):
        return functions[operator](self.operand_stack)

    def output_operand(self, operand):
        self.operand_stack.append(operand)

    def _handle_closing_parenthesis(self, operator_stack):
        while True:
            if not operator_stack:
                raise ExprError("unbalanced parenthesis")
            char = operator_stack.pop()
            if char == "(":
                break
            self.output_operator(char)

    def _convert_to_unary_operator(self, last_operator, operator):
        if last_operator and last_operator != ")":
            if operator == "-":
                operator = UMinus
            elif operator == "+":
                operator = UPlus
        return operator

    def _process_expression_elements(self, operand, operator, operator_stack, last_operand, last_operator):
        if operand in ("e",
                       "E") and (last_operand or last_operator == ")"):
            operand, operator = operator, operand

        if operand:
            if last_operand:
                raise ExprError("expected operator")
            self.output_operand(self.as_float_or_int(operand))
        elif operator == "(":
            operator_stack.append("(")
        elif operator == ")":
            self._handle_closing_parenthesis(operator_stack)
        elif operator in precedence:
            operator = self._convert_to_unary_operator(last_operator, operator)
            is_unary = operator in unary_ops
            prec = precedence[operator]
            while not is_unary and operator_stack and prec <= precedence[operator_stack[-1]]:
                char = operator_stack.pop()
                self.output_operator(char)
            operator_stack.append(operator)
        else:
            raise ExprError(f"unknown operator: {operator!r}")

        last_operand, last_operator = operand, operator
        return last_operand, last_operator, operand, operator

    def parse_expr(self, expr_to_parse):
        tokens = tokenize(expr_to_parse)
        if not tokens:
            return ""

        self.operand_stack = []
        operator_stack = []

        last_operand, last_operator = False, True

        for operand, operator in tokens:
            last_operand, last_operator, operand, operator = self._process_expression_elements(operand, operator, operator_stack,
                                                                                               last_operand, last_operator)

        while operator_stack:
            popped_operator = operator_stack.pop()
            if popped_operator == "(":
                raise ExprError("unbalanced parenthesis")
            self.output_operator(popped_operator)

        if len(self.operand_stack) != 1:
            raise ExprError(f"bad stack: {self.operand_stack}")

        return self.operand_stack[-1]


_cache = {}


def expr(char):
    try:
        return _cache[char]
    except KeyError:
        pass

    parsed_expr = Expr().parse_expr(char)
    _cache[char] = parsed_expr
    return parsed_expr


def main():
    while True:
        input_string = input("> ")
        if not input_string:
            continue

        stime = time.time()
        try:
            res = expr(input_string)
        except Exception as err:
            print("ERROR:", err)
            traceback.print_exc()

            continue
        print(res)
        print(time.time() - stime, "s")


if __name__ == "__main__":
    main()
