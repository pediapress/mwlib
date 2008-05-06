// -*- mode: c++ -*-
// Copyright (c) 2007-2008 PediaPress GmbH
// See README.txt for additional licensing information.

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
	t_newline,
	t_column,
	t_row,
	t_tablecaption,
	t_urllink,
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
		line_startswith_section = -1;
		tablemode=0;
	}

	int found(mwtok val) {
		if (val==t_text && tokens.size()) {
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

	bool bol() const {
		return (start==source) || (start[-1]=='\n');
	}

	bool eol() const {
		return *cursor=='\n' || *cursor==0;
	}

	void newline() {
		if (line_startswith_section>=0) {
			tokens[line_startswith_section].type = t_text;
		}
		line_startswith_section = -1;
	}

	inline int scan();

	Py_UNICODE *source;

	Py_UNICODE *start;
	Py_UNICODE *cursor;
	Py_UNICODE *end;
	vector<Token> tokens;

	int line_startswith_section;
	int tablemode;
};


int Scanner::scan()
{
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

/*
  the re2c manpage says:
  "The user must arrange for a sentinel token to appear at the end of input"
  \000 is our sentinel token.
*/

/*!re2c
  any = [^\000];
  ftp = "ftp://" [-a-zA-Z0-9_+${}~?=/@#&*(),:.]+ ;
  mailto = "mailto:" [-a-zA-Z0-9_!#$%*./?|^{}`~&'+=]+ "@" [-a-zA-Z0-9_.]+ ;
  url = "http" "s"? "://" [-\xe4\xc4\xf6\xd6\xfc\xdca-zA-Z_0-9./?=&:%:~()#+,]+ ;
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
*/
	if (!bol()) {
		goto not_bol;
	}
/*!re2c
  " "* "{|"              {++tablemode; RET(t_begin_table);}
  " "* "|}"              {--tablemode; RET(t_end_table);}

  " "* "|" "-"+         
	{
		if (tablemode) 
			RET(t_row);
		if (*start==' ') {
			cursor = start+1;
			RET(t_pre);
		}
		RET(t_text);
	}

  " "* ("|" | "!")      
	{
		if (tablemode)
			RET(t_column);

		if (*start==' ') {
			cursor = start+1;
			RET(t_pre);
		}
		RET(t_text);
	}

  " "* "|" "+"+         
	{
		if (tablemode) 
			RET(t_tablecaption);
		if (*start==' ') {
			cursor = start+1;
			RET(t_pre);
		}
		RET(t_text);
	}

  " "		{RET(t_pre);}
  "="+ [ \t]*   {
			line_startswith_section = found(t_section);
			return t_section;
		}
  ":"* [#*]+    {RET(t_item);}
  ":"+          {RET(t_colon);}
  ";"+          {RET(t_semicolon);}
  "-"{4,}       {RET(t_hrule);}

  [^]           {goto not_bol;}
 */


not_bol:
	cursor = save_cursor;
	marker = cursor;

/*!re2c
  "[" mailto {RET(t_urllink);}
  mailto {RET(t_http_url);}
  "[" ftp {RET(t_urllink);}
  ftp           {RET(t_http_url);}
  "[" url {RET(t_urllink);}
  url 		{RET(t_http_url);}
  magicword		{RET(t_magicword);}
  [a-zA-Z0-9_]+				{RET(t_text);}
  "[["              {RET(t_2box_open);}
  "]]"              {RET(t_2box_close);}
  "="+ [ \t]*       {
			if (eol()) {
			        if (line_startswith_section>=0) {
				     line_startswith_section=-1;
				     RET(t_section_end);
                                } else {
				     RET(t_text);
                                }
			} else {
				RET(t_text);
			}
		    }
  "\n"{2,}	    {newline(); RET(t_break);}
  "\n"		    {newline(); RET(t_newline);}
  "||" | "|!" | "!!"              
	{
		if (tablemode) 
			RET(t_column);
		cursor = start+1;
		RET(t_special);
	}
  "|+"              
	{
		if (tablemode) 
			RET(t_tablecaption);
		cursor = start+1;
		RET(t_special);
	}
  [:|\[\]]              {RET(t_special);}
  "'''''" | "'''" | "''"  {RET(t_style);}
  "<" "/"? [a-zA-Z]+ [^\000<>]* "/"? ">" 
		{RET(t_html_tag);}

  "<!--"[^\000<>]*"-->"
                {RET(t_comment);}
  entity        {RET(t_entity);}

  "\000"  {newline(); return t_end;}
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



extern "C" {
	DL_EXPORT(void) init_mwscan();
}

DL_EXPORT(void) init_mwscan()
{
	/*PyObject *m =*/ Py_InitModule("_mwscan", module_functions);
}
