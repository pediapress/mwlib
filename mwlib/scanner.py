#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

"""this file implements a lexical scanner for mediawiki markup.
Note that it currently is lossy, i.e. some constructs such as 
comments won't appear in it's output.
"""

import sys
import StringIO
import htmlentitydefs

from Plex import TEXT, IGNORE, Begin
from Plex import Lexicon, State
from Plex import RE, Seq, Alt, Rep1, Empty, Str, Any, AnyBut, AnyChar, Range
from Plex import Opt, Rep, Bol, Eol, Eof, Case, NoCase
from Plex import Scanner

magic_tag = 'a7831d532a30df0cd772bbc895944ec1'


_special = '#*_=:|[]<>!(){}\'&\n; '
notspecial = AnyBut(_special)
special = Any(_special)

url = Alt(Str("http")+Opt(Str("s"))+Str("://")+Rep1((Any("|\\()~/?!#&=%:_.-+,';*")|Range("AZaz09"))),
          Str("mailto:")+Rep1(Range("azAZ09")|Any(".-@")))

alnum = Range("AZaz09")

ws = Rep(Any(" \n"))
tag_value = (ws+Rep1(alnum|Str(":"))+ws+Str("=")+ws+
             ((Str('"')+Rep(AnyBut('"'))+Str('"')) |
              (Str("'")+Rep(AnyBut("'"))+Str("'")) |
              Rep1(AnyBut(' \n;>')))
             +ws)
tag_values = Rep(tag_value)

## Permitted HTML

## The following HTML elements are currently permitted:

##     * <b>
##     * <big>
##     * <blockquote>
##     * <br>
##     * <caption>
##     * <center>
##     * <cite>
##     * <code>
##     * <dd>
##     * <div>
##     * <dl>
##     * <dt>
##     * <em>
##     * <font>
##     * <h1>

##     * <h2>
##     * <h3>
##     * <h4>
##     * <h5>
##     * <h6>
##     * <hr>
##     * <i>
##     * <li>
##     * <ol>
##     * <p>
##     * <pre>
##     * <rb>
##     * <rp>
##     * <rt>
##     * <ruby>

##     * <s>
##     * <small>
##     * <strike>
##     * <strong>
##     * <sub>
##     * <sup>
##     * <table>
##     * <td>
##     * <th>
##     * <tr>
##     * <tt>
##     * <u>
##     * <ul>
##     * <var>
##     * <!-- ... -->

tagnames = """timeline table nowiki i br hr b sup sub big small u span s li ol ul cite code font
div includeonly tt center references math ref gallery td tr th p blockquote pre
strong var caption""".split()

tagnames.append(magic_tag)
tagnames.append("index")

    
assert "" not in tagnames
assert len(set(tagnames)) == len(tagnames), "duplicate entries"

# htmltag = NoCase(Str("<")+Opt(Str("/"))+Alt(*[Str(x) for x in tagnames])+Opt(Rep1(Any(" \n"))+Opt(tag_values)) + Rep(Any(" \n"))+Opt(Str("/"))+Str(">"))
htmltagval = Rep(Rep(AnyBut('<>"')) | Str('"')+Rep(AnyBut('"'))+Str('"'))
htmltag = NoCase(Str("<")+Opt(Str("/"))+Alt(*[Str(x) for x in tagnames])+Opt(Any(" \n")+htmltagval)+Opt(Str("/"))+Str(">"))
                 
def resolveEntity(scanner, text):
    e = text[1:-1]
    cp = htmlentitydefs.name2codepoint.get(e, None)
    if cp:
        scanner.produce("TEXT", unichr(cp))

def resolveNumericEntity(scanner, text):
    e = text[2:-1]    
    cp = int(e)
    scanner.produce("TEXT", unichr(cp))

def resolveHexEntity(scanner, text):
    cp = int(text[3:-1], 16)
    scanner.produce("TEXT", unichr(cp))
    
    

def ident(s):
    return (Str(s), s)

def maybe_vlist(token):
    def f(scanner, text):
        if scanner.tablemode:
            return token
        else:
            if text[:1]==' ':
                scanner.produce("PRE", " ")
                scanner.produce("TEXT", text[1:])
            else:
                return "TEXT"
        
    return f

def endpre(scanner, text):
    scanner.begin("")
    scanner.produce(EndTagToken("pre", text))

    
def begin_gallery(scanner, text):
    scanner.produce("GALLERY")
    scanner.begin("GALLERY")

def end_gallery(scanner, text):
    scanner.produce("ENDGALLERY")
    scanner.begin("")
    
    
def begin_table(scanner, text):
    scanner.tablemode += 1
    return "BEGINTABLE"

def end_table(scanner, text):
    scanner.tablemode -= 1
    return "ENDTABLE"
    

def begin_math(scanner, text):
    scanner.begin("MATH")
    scanner.produce("MATH")

def end_math(scanner, text):
    scanner.begin("")
    scanner.produce("ENDMATH")    

def end_timeline(scanner, text):
    scanner.begin("")
    scanner.produce("TIMELINE")

def hrule(scanner, text):
    scanner.produce(TagToken("hr", "<hr>"), "<hr>")

def tag(name):
    return NoCase(Str("<")+Opt(Str("/"))+Str(name)+Rep(Str(" "))
                  +Opt(tag_values) + Str(">"))

def begin_tag(name):
    return NoCase(Str("<")+Rep(Str(" "))+Str(name)+Rep(AnyBut(">"))+Str(">"))

def end_tag(name):
    return NoCase(Str("</")+Str(name)+Rep(AnyBut(">"))+Str(">"))

class _BaseTagToken(object):
    def __eq__(self, other):
        if isinstance(other, basestring):
            return self.t == other
        if isinstance(other, self.__class__):
            return self.t == other.t
        return False

    def __ne__(self, other):
        return not(self==other)
    
    def __hash__(self):
        return hash(self.t)

class TagToken(_BaseTagToken):
    values = {}
    def __init__(self, t, text=''):
        self.t = t
        self.text = text

    def __repr__(self):
        return "<Tag:%s %r>" % (self.t, self.text)

class EndTagToken(_BaseTagToken):
    def __init__(self, t, text=''):
        self.t = t
        self.text = text
        
    def __repr__(self):
        return "<EndTag:%s>" % self.t


class TagAnalyzer(object):
    ignore_tags = set(['code', 'font', 'includeonly', 'center', 'p', 'caption'])
    def analyzeTag(self, scanner, text):
        selfClosing = False
        if text.startswith(u"</"):
            name = text[2:-1]
            klass = EndTagToken
            isEndToken = True
        elif text.endswith("/>"):
            name = text[1:-2]
            klass = TagToken
            selfClosing = True
            isEndToken = False # ???
        else:
            name = text[1:-1]
            klass = TagToken
            isEndToken = False

        name, values = (name.split(None, 1)+[u''])[:2]
        from mwlib.parser import paramrx
        values = dict(paramrx.findall(values))
        name = name.lower()

        if name in self.ignore_tags:
            return None

        if name=='br' or name=='references':
            isEndToken = False
            klass = TagToken
            
        if name=='table':
            if isEndToken:
                return "ENDTABLE"
            else:
                return "BEGINTABLE"

        if name=='th' or name=='td':
            if isEndToken:
                return
            else:
                return "COLUMN"

        if name=='tr':
            if isEndToken:
                return
            else:
                return "ROW"
        

        if name=='timeline':
            if not isEndToken:
                scanner.begin("TIMELINE")
                scanner.produce("TIMELINE")
            return
        
        if name=="math":
            if isEndToken:
                return
            else:
                return begin_math(scanner, text)
            
        if name=="gallery":
            if isEndToken:
                return
            else:
                return begin_gallery(scanner, text)

        if name == "pre":
            scanner.begin("pre")
            
        r = klass(name, text)
        r.selfClosing = selfClosing
        r.values = values
        return r

analyzeTag = TagAnalyzer().analyzeTag        


def eolstyle(scanner, text):
    text = text[1:]
    scanner.produce("EOLSTYLE", text)
    

default = [
    (Str("{{"), Begin('WIKI_SPECIAL')),
    (Str("<!--"), Begin('comment')),
    (NoCase(Str("<nowiki>")), Begin("nowiki")),
    (NoCase(Str("<nowiki"))+Rep(Str(" ")) +Str("/>"), IGNORE),
    (Str("&")+Rep1(Range("AZaz09"))+Str(";"), resolveEntity),
    (Str("&#")+Rep1(Range("09"))+Str(";"), resolveNumericEntity),
    (Str("&#")+NoCase(Str('x'))+Rep1(Range("afAF09"))+Str(";"), resolveHexEntity),
    
    (Str("__TOC__"), IGNORE),
    (Str("__NOTOC__"), IGNORE),
    (Str("__FORCETOC__"), IGNORE),
    (Str("__NOEDITSECTION__"), IGNORE),
    (Str("__START__"), IGNORE),
    (Str("__END__"), IGNORE),
    ident("[["),
    ident("]]"),
    (Str("[")+url, "URLLINK"),
    (Str("[#")+Rep1(Range("AZaz09")|Str("_"))+Str("]"), IGNORE),
    (url, "URL"),
    (Bol+Str("----")+Rep(Str("-")), hrule),
    (Str("''"), "STYLE"),
    (Str("'''"), "STYLE"),
    (Str("'''''"), "STYLE"),
    (Bol+Rep1(Str('=')), 'SECTION'),
    (Rep1(Str('=')), 'ENDSECTION'),
    (Rep(Str(" "))+Str("{|"), begin_table),
    (Rep(Str(" "))+Str("|}"), end_table),
    (Bol+Rep(Str(" "))+Str("|"), maybe_vlist("COLUMN")),
    (Bol+Rep(Str(" "))+Str("!"), maybe_vlist("COLUMN")),
    (Str("||"), maybe_vlist("COLUMN")),
    (Str("|!"), maybe_vlist("COLUMN")),
    (Str("!!"), maybe_vlist("COLUMN")),
    (Str("|+"), maybe_vlist("TABLECAPTION")),
    (Bol+Rep(Str(" "))+Str("|")+Rep1(Str("-")), maybe_vlist("ROW")),
    (Str("\n\n")+Rep(Str("\n")), "BREAK"),
    ident("\n"),
    (Bol+Rep(Str(":"))+Rep1(Str("*")), 'ITEM'),
    (Bol+Rep(Str(":"))+Rep1(Str("#")), 'ITEM'),
    (Str("\x00")+Rep1(Str(":")), eolstyle),
    (Str("\x00")+Rep1(Str(";")), eolstyle),    
    (Bol+Rep1(Str(":")), "EOLSTYLE"),
    (Bol+Rep1(Str(";")), "EOLSTYLE"),
    (Bol+Str(' '), 'PRE'),
    (htmltag, analyzeTag),    
    (Rep1(notspecial), "TEXT"),
    (special, 'SPECIAL'),
]


lex = Lexicon(default+[    
    State("nowiki", [
          (NoCase(Str("</nowiki>")), Begin('')),
          (Rep1(AnyBut("<")), "TEXT"),
          (Str("<"), "TEXT"),
    ]),

    State("pre", [
          (Str("</pre>"), endpre),
          (Str("&")+Rep1(Range("AZaz09"))+Str(";"), resolveEntity),
          (Str("&#")+Rep1(Range("09"))+Str(";"), resolveNumericEntity),
          (Str("&#")+NoCase(Str('x'))+Rep1(Range("afAF09"))+Str(";"), resolveHexEntity),          
          (Rep1(AnyBut("<&")), "TEXT"),
          (Any("<&"), "TEXT"),
    ]),
    

    State("TIMELINE",[
          (end_tag("timeline"), end_timeline),
          (Rep1(AnyBut("<")), "TEXT"),
          (Str("<"), "TEXT"),
    ]),
    
    
    State("MATH", [
        (Rep1(AnyBut("<")), "LATEX"),
        (Str("<"), "LATEX"),
        (end_tag("math"), end_math),
        ]),
        
    State('WIKI_SPECIAL', [
          (Str("}}"), Begin('')),
          (AnyChar, IGNORE)]),


    State("GALLERY", [
        ident("[["),
        ident("]]"),
        (end_tag("gallery"), end_gallery),        
        (special, 'SPECIAL'),        
        (Rep1(notspecial), "TEXT"),
        ident("\n"),
    ]),
    
    State('comment', [
          (Str("-->"), Begin('')),
          (AnyChar, IGNORE)])
    ])




def tokenize(name, input):
    assert input is not None, "must specify input argument in tokenize"
    if input is None:
        input = unicode(open(name).read(), 'utf8')

    

    if isinstance(input, basestring):
        input = StringIO.StringIO(input)
    s=Scanner(lex, input, name)
    s.tablemode = 0
    
    
    tokens = []
    while 1:
        token = s.read()
        if token[0] is None:
            break
        tokens.append(token)
        
    return tokens

    

def main():
    import time
    
    for x in sys.argv[1:]:
        stime = time.time()
        tokens = tokenize(sys.argv[1], None)
        print "tokenizing:", time.time()-stime, "%s tokens" % len(tokens)
        for t in tokens:
            print t
        print "---------------"    
        
        
    
if __name__=="__main__":
    main()
