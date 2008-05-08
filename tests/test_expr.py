#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import math
from mwlib.expander import expandstr

def ee(s, expected=None):
    s=expandstr("{{#expr:%s}}" % (s,))
    if isinstance(expected, (float,int,long)):
        assert math.fabs(float(s)-expected)<1e-5
    elif expected is not None:
        assert s==expected, "expected %r, got %r" % (expected, s)
        
    return s

        
def test_pi():
    ee('pI', math.pi)
    ee('PI', math.pi)
    ee('pi*2', math.pi*2)
    ee('pi+1', math.pi+1)

def test_e():
    ee('e', math.e)
    ee('E', math.e)
    ee("e+1", math.e+1)
    ee("2*e", math.e*2)
    
def test_pow():
    ee("2^5", 32)
    ee("-2^4", 16)
    
def test_ln():
    ee("ln 2.7182818284590451", 1)
    
def test_exp():
    ee("exp(1)", 2.7182818284590451)
    ee("exp(0)", 1)
    
def test_abs_int():
    ee("abs(-5)", "5")

def test_abs():
    ee("abs(-3.0)", 3.0)
    ee("abs(3.0)", 3.0)
    ee("abs 1-3", -2)

def test_sin():
    ee("sin 3.1415926535897931", 0)

def test_cos():
    ee("cos 3.1415926535897931", -1)

def test_tan():
    ee("tan 3.1415926535897931", 0)
    ee("tan 0.785398163397", 1)

def test_asin():
    ee("asin 0.5", 0.5235987755983)
    ee("asin 0", 0)
    
def test_acos():
    ee("acos 0", 1.5707963267949)
    ee("acos 0.5", 1.0471975512)
    
def test_atan():
    ee("atan 0", 0)
    ee("atan 1", 0.785398163397)

def test_floor():
    ee("floor 5.1", "5")
    ee("floor -5.1", "-6")
    
def test_trunc():
    ee("trunc 5.1", "5")
    ee("trunc -5.1", "-5")

def test_ceil():
    ee("ceil 5.1", "6")
    ee("ceil -5.1", "-5")
    
def test_scientific():
    ee("1e25", "1.0E+25")
    ee("1E25", "1.0E+25")
    ee("1e-10", "1.0E-10")
    ee("1E-10", "1.0E-10")

def test_unary_double_plus():
    ee("++5", 5)
    
def test_unary_double_minus():
    ee("--5", 5)

def test_unary_plus():
    ee("0-+5", -5)
    
def test_mod_unary():
    ee("--1.253702 mod 360", 1)
    
def test_mod():
    ee("1.253702 mod 360", 1)

def test_unary_paren():
    ee("10+(--100)", 110)
    
def test_unary_pow_minus():
    ee("2^-10", 0.0009765625)
    
def test_unary_pow_plus():
    ee("2^+10", 1024)
    
