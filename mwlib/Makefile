all: _mwscan.so

_mwscan.so: _mwscan.cc
	(cd .. && python ./setup.py build_ext --inplace build)

_mwscan.cc: _mwscan.re
	re2c -w -o _mwscan.cc  _mwscan.re

clean::
	rm -rf *.pyc *~ *.so build a.out _mwscan.cc

