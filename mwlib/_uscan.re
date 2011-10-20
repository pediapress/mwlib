// -*- mode: c++ -*-
// Copyright (c) 2007-2009 PediaPress GmbH
// See README.rst for additional licensing information.

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
	t_singlequote,
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
	t_uniq,

	t_ebad,
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
		last_ebad = false;
	}

	int found(mwtok val) {
		if (val==t_ebad) {
			last_ebad=true;
			return tokens.size()-1;
		}

		if (val==t_text && tokens.size() && !last_ebad) {
			Token &previous_token (tokens[tokens.size()-1]);
			if (previous_token.type==val) {
				previous_token.len += cursor-start;
				return tokens.size()-1;
			}
		}
		
		last_ebad = false;

		Token t;
		t.type = val;
		t.start = (start-source);
		t.len = cursor-start;			
		tokens.push_back(t);
		return tokens.size()-1;
	}

	bool bol() {
		if ((start==source) || (start[-1]=='\n')) {
			memset(&lineflags, 0, sizeof(lineflags));
			return true;
		} else {
			return false;
		}
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

	bool last_ebad;
	int line_startswith_section;
	int tablemode;
	struct {
		int rowchar;
	} lineflags;
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
  any = [^\000\XEBAD];
  ftp = "ftp://" [-a-zA-Z0-9_+${}~?=/@#&*(),:.']+ ;
  mailto = "mailto:" [-a-zA-Z0-9_!#$%*./?|^{}`~&'+=]+ "@" [-a-zA-Z0-9_.]+ ;
  irc = "irc://" [a-zA-Z0-9./]+ ;
  news = "news:" [a-ZA-Z0-9.]+ ;
  url = "http" "s"? "://" [^\X005D[<>"\X0000-\X0020\X007F]+;
  entity_name = "&" [a-zA-Z0-9]+ ";";
  entity_hex = "&#" 'x' [a-fA-F0-9]+ ";";
  entity_dec = "&#" [0-9]+ ";";

  entity = (entity_name | entity_hex | entity_dec);


  magicword = ( "__TOC__" 
	      | "__NOTOC__"
	      | "__NOINDEX__"
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
	      | "__NUMBEREDHEADINGS__"
	      | "__NOTOCNUM__"
	      | "__NONUMBEREDHEADINGS__"
	      );
*/
	if (!bol()) {
		goto not_bol;
	}
/*!re2c
  [ \t]* ":"* "{|"              {++tablemode; RET(t_begin_table);}
  [ \t]* "|}"              {if (--tablemode<0) tablemode=0; RET(t_end_table);}

  [ \t]* "|" "-"+         
	{
		if (tablemode) 
			RET(t_row);
		if (*start==' ') {
			cursor = start+1;
			RET(t_pre);
		}
		RET(t_text);
	}

  [ \t]* ("|" | "!")      
	{
		if (tablemode) {
		        lineflags.rowchar=cursor[-1];
			RET(t_column);
		}

		if (*start==' ') {
			cursor = start+1;
			RET(t_pre);
		}
		RET(t_text);
	}

  [ \t]* "|" "+"+         
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
  [:;#*]+    {RET(t_item);}
  "-"{4,}       {RET(t_hrule);}

  [^]           {goto not_bol;}
 */


not_bol:
	cursor = save_cursor;
	marker = cursor;

/*!re2c
  "\XEBAD" {RET(t_ebad);} 
  "[" mailto {RET(t_urllink);}
  mailto {RET(t_http_url);}
  "[" irc {RET(t_urllink);}
  irc {RET(t_http_url);}
  "[" news {RET(t_urllink);}
  news {RET(t_http_url);}
  "[" ftp {RET(t_urllink);}
  ftp           {RET(t_http_url);}
  "[" url {RET(t_urllink);}
  url 		{RET(t_http_url);}
  magicword		{RET(t_magicword);}
  "\X007F" "UNIQ-" [a-z0-9]+ "-" [0-9]+ "-" [0-9a-f]+ "-QINU" "\X007f" {RET(t_uniq);}

  [a-zA-Z0-9]+				{RET(t_text);}
  "_"+                     {RET(t_text);}
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
  "\n" ("\n" | " ")* "\n"	    
		{newline();
		 Py_UNICODE *tmp = cursor;

		 cursor = start+1;
		 found(t_newline);
		 start += 1;
		 cursor = tmp;  
		 RET(t_break);
		}
  "\n"		    {newline(); RET(t_newline);}
  "||" | "|!" | "!!"              
	{
		if (tablemode) {
		        if (cursor[-2]!='!' || cursor[-2]==lineflags.rowchar) {
			       RET(t_column);
			}
		}
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
  "'" "'"+ {RET(t_singlequote);}
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
	DL_EXPORT(void) init_uscan();
}

DL_EXPORT(void) init_uscan()
{
	/*PyObject *m =*/ Py_InitModule("_uscan", module_functions);
}
