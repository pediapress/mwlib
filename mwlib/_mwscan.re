// -*- mode: c++ -*-

#include <Python.h>

#include <iostream>
#include <assert.h>
#include <vector>
using namespace std;

#define RET(x) {found(x); return x;}

typedef enum {
	t_end,
	t_text,
	t_entity,
	t_special,
	t_magicword,
	t_comment,
	t_2box_open,   // [[
	t_2box_close,  // ]]
	t_http_url,
	t_break,
	t_begin_table,
	t_end_table,
	t_html_tag,
	t_style,
	t_pre,
	t_section,
	t_section_end,
	t_item,
	t_colon,
	t_semicolon,
	t_hrule,
} mwtok;

struct Token
{
	int type;
	int start;
	int len;
};

class Scanner
{
public:

	Scanner(Py_UNICODE *_start, Py_UNICODE *_end) {
		source = start = _start;
		end = _end;
		cursor = start;
	}

	void found(mwtok val) {
		if (val==t_text && tokens.size()) {
			Token &previous_token (tokens[tokens.size()-1]);
			if (previous_token.type==val) {
				previous_token.len += cursor-start;
				return;
			}
		}
		Token t;
		t.type = val;
		t.start = (start-source);
		t.len = cursor-start;			
		tokens.push_back(t);
	}
	bool bol() const {
		return (start==source) || (start[-1]=='\n'); // XXX
	}

	bool eol() const {
		return cursor>=end || *cursor=='\n' || *cursor==0;
	}
	inline int scan();

	Py_UNICODE *source;

	Py_UNICODE *start;
	Py_UNICODE *cursor;
	Py_UNICODE *end;
	vector<Token> tokens;
};


int Scanner::scan()
{
	start=cursor;
	Py_UNICODE *marker=cursor;

#define YYCTYPE         Py_UNICODE
#define YYCURSOR        cursor
#define YYMARKER	marker
#define YYLIMIT   (end)
#define YYFILL(n) return 0;

/*
  the re2c manpage says:
  "The user must arrange for a sentinel token to appear at the end of input"
  \000 is our sentinel token.
*/

/*!re2c
  any = [^\000];
  entity_name = "&" [a-zA-Z0-9]+ ";";
  entity_hex = "&#" 'x' [a-fA-F0-9]+ ";";
  entity_dec = "&#" [0-9]+ ";";

  entity = (entity_name | entity_hex | entity_dec);


  magicword = ( "__TOC__" 
	      | "__NOTOC__"
	      | "__FORCETOC__"
	      | "__NOEDITSECTION__"
	      | "__NEWSECTIONLINK__"
	      | "__NOCONTENTCONVERT__"
	      | "__NOCC__"
	      | "__NOGALLERY__"
	      | "__NOTITLECONVERT__"
	      | "__NOTC__"
	      | "__END__" 
	      | "__START__"
	      );

  "http" "s"? "://" [-a-zA-Z_0-9./?=&:%]+		{RET(t_http_url);}
  magicword		{RET(t_magicword);}
  [a-zA-Z0-9_]+				{RET(t_text);}
  "[["              {RET(t_2box_open);}
  "]]"              {RET(t_2box_close);}
  "="+ [ \t]*       {
			if (bol()) {
				RET(t_section);
			} else if (eol()) {
				RET(t_section_end);
			} else {
				RET(t_text);
			}
		    }
  ":"* [#*]+        {if (bol()) RET(t_item) else RET(t_text);}
  ":"+              {if (bol()) RET(t_colon) else RET(t_text);}
  ";"+              {if (bol()) RET(t_semicolon) else RET(t_text);}
  "-"{4,}           {if (bol()) RET(t_hrule) else RET(t_text);}
  "\n"{2,}	    {RET(t_break);}
  "\n"		    {RET(t_text);}
  "{|"              {RET(t_begin_table);}
  "|}"              {RET(t_end_table);}
  "'''''" | "'''" | "''"  {RET(t_style);}
  "<" "/"? [a-zA-Z]+ [^\000<>]* "/"? ">" 
		{RET(t_html_tag);}

  "<!--"[^\000<>]*"-->"
                {RET(t_comment);}
  entity        {RET(t_entity);}

  " "		{
			if (bol()) { 
			   RET(t_pre);
			} else {
			   RET(t_text);
			}
		}

  "\000"  {return t_end;}
    .		    {RET(t_text);}
*/
}


PyObject *py_scan(PyObject *self, PyObject *args) 
{
	PyObject *arg1;
	if (!PyArg_ParseTuple(args, "O:mwscan.scan", &arg1)) {
		return 0;
	}
	PyUnicodeObject *unistr = (PyUnicodeObject*)PyUnicode_FromObject(arg1);
	if (unistr == NULL) {
		PyErr_SetString(PyExc_TypeError,
				"parameter cannot be converted to unicode in mwscan.scan");
		return 0;
	}

	Py_UNICODE *start = unistr->str;
	Py_UNICODE *end = start+unistr->length;
	

	Scanner scanner (start, end);
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



extern "C" void init_mwscan(void);

DL_EXPORT(void) init_mwscan(void)
{
	/*PyObject *m =*/ Py_InitModule("_mwscan", module_functions);
}
