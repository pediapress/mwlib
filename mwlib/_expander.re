// -*- mode: c++ -*-
// Copyright (c) 2007-2009 PediaPress GmbH
// See README.rst for additional licensing information.

#include <Python.h>

#include <iostream>
#include <assert.h>
#include <vector>

using namespace std;

#define RET(x) {found(x); return x;}

struct Token
{
	int type;
	int start;
	int len;
};


class MacroScanner
{
public:

	MacroScanner(Py_UNICODE *_start, Py_UNICODE *_end) {
		source = start = _start;
		end = _end;
		cursor = start;
	}

	int found(int val) {
		if (val==5 && tokens.size()) {
			Token &previous_token (tokens[tokens.size()-1]);
			if (previous_token.type==val) {
				previous_token.len += cursor-start;
				return tokens.size()-1;
			}
		}
		Token t;
		t.type = val;
		t.start = (start-source);
		t.len = cursor-start;			
		tokens.push_back(t);
		return tokens.size()-1;
	}

	inline int scan();

	Py_UNICODE *source;

	Py_UNICODE *start;
	Py_UNICODE *cursor;
	Py_UNICODE *end;
	vector<Token> tokens;
};


int MacroScanner::scan()
{

def:

	start=cursor;
	
	Py_UNICODE *marker=cursor;

	Py_UNICODE *save_cursor = cursor;


#define YYCTYPE         Py_UNICODE
#define YYCURSOR        cursor
#define YYMARKER	marker
#define YYLIMIT   (end)
// #define YYFILL(n) return 0;

/*!re2c
re2c:yyfill:enable = 0 ;
*/



/*!re2c
  "{"{2,}          {RET(1);}
  "}"{2,}          {RET(2);}
  "[[" | "]]"      {RET(3);}
  "|"              {RET(6);}

  '<noinclude>'    {goto noinclude;}
  '<nowiki>'       {goto nowiki;}
  '<imagemap' [^<>\000]* '>' {goto imagemap;}
  '<math' [^<>\000]* '>' {goto math;}
  '<gallery' [^<>\000]* '>' {goto gallery;}
 
  "<!--[^\000<>]*-->" {RET(5);}

  "\000" {RET(0);}
  [^\000] {RET(5);}

 */



noinclude:
/*!re2c
	'</noinclude>' {goto def;}
	[^\000] {goto noinclude;}
	"\000" {cursor=start+11; RET(5);}
 */

nowiki:
/*!re2c
	'</nowiki>' {RET(5);}
	[^\000] {goto nowiki;}
	"\000" {RET(0);}
 */

math:
/*!re2c
	'</math>' {RET(5);}
	[^\000] {goto math;}
	"\000" {RET(0);}
 */

gallery:
/*!re2c
	'</gallery>' {RET(5);}
	[^\000] {goto gallery;}
	"\000" {RET(0);}
 */

imagemap:
/*!re2c
	'</imagemap>' {RET(5);}
	[^\000] {goto imagemap;}
	"\000" {RET(0);}
 */

pre:
/*!re2c
	'</pre>' {RET(5);}
	[^\000] {goto pre;}
	"\000" {RET(0);}
 */
	
}


PyObject *py_scan(PyObject *self, PyObject *args) 
{
	PyObject *arg1;
	if (!PyArg_ParseTuple(args, "O:_expander.scan", &arg1)) {
		return 0;
	}
	PyUnicodeObject *unistr = (PyUnicodeObject*)PyUnicode_FromObject(arg1);
	if (unistr == NULL) {
		PyErr_SetString(PyExc_TypeError,
				"parameter cannot be converted to unicode in _expander.scan");
		return 0;
	}

	Py_UNICODE *start = unistr->str;
	Py_UNICODE *end = start+unistr->length;
	

	MacroScanner scanner (start, end);
	Py_BEGIN_ALLOW_THREADS
	while (scanner.scan()) {
	}
	Py_END_ALLOW_THREADS
	Py_XDECREF(unistr);
	
	// return PyList_New(0); // uncomment to see timings for scanning

	int size = scanner.tokens.size();
	PyObject *result = PyList_New(size);
	if (!result) {
		return 0;
	}
	
	for (int i=0; i<size; i++) {
		Token t = scanner.tokens[i];
		PyList_SET_ITEM(result, i, Py_BuildValue("iii", t.type, t.start, t.len));
	}
	
	return result;
}



static PyMethodDef module_functions[] = {
	{"scan", (PyCFunction)py_scan, METH_VARARGS, "scan(text)"},
	{0, 0},
};



extern "C" {
	DL_EXPORT(void) init_expander();
}

DL_EXPORT(void) init_expander()
{
	/*PyObject *m =*/ Py_InitModule("_expander", module_functions);
}
