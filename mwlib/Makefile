RE2C = re2c -w --no-generation-date

default:: _mwscan.cc

all:: _expander.cc _mwscan.cc _mwscan.so _expander.so

_expander.so: _expander.cc
	(cd .. && python ./setup.py build_ext --inplace build)

_mwscan.so: _mwscan.cc
	(cd .. && python ./setup.py build_ext --inplace build)

_expander.cc: _expander.re
	$(RE2C)	-o _expander.cc  _expander.re

_mwscan.cc: _mwscan.re
	$(RE2C) -o _mwscan.cc  _mwscan.re

clean::
	rm -rf *.pyc *~ *.so build a.out


