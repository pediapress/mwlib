"""
converts LaTex to Mathml using blahtexml

FIXME: Robustness, error handling, ....
# see integration in MW: 
http://cvs.berlios.de/cgi-bin/viewcvs.cgi/blahtex/blahtex/includes/Math.php?rev=HEAD&content-type=text/vnd.viewcvs-markup

FIXME: replace with texvc which is deistributed with MediaWiki


"""
import sys
import popen2
try:
    import xml.etree.ElementTree as ET
except:
    from elementtree import ElementTree as ET
from xml.parsers.expat import ExpatError


def log(err):
    sys.stderr.write(err + " ")
    pass


def latex2mathml(latex):

    data = "\\displaystyle\n%s\n" %  latex.strip()  
    r, w, e = popen2.popen3('blahtexml --mathml')
    w.write(data)
    w.close()
    errormsg = e.read()
    outmsg = r.read()
    r.close()
    e.close()

    if outmsg:
        # ET has unreadable namespace handling
        # http://effbot.org/zone/element.htm#xml-namespaces
        #ET._namespace_map["http://www.w3.org/1998/Math/MathML"] = 'mathml'
        # remove xmlns declaration
        #outmsg = outmsg.replace('xmlns="http://www.w3.org/1998/Math/MathML"', '')

        outmsg = '<?xml version="1.0" encoding="UTF-8"?>\n' + outmsg
        #print repr(outmsg)
    
        try:
            p =  ET.fromstring(outmsg)
        except ExpatError:
            log("\n\nparsing failed\n\n" )
            log(latex +"\n\n")
            log(data +"\n\n")
            log(errormsg +"\n")
            log(outmsg +"\n")
            return 
            

        tag = "mathml"
        mathml = p.getiterator(tag)
        
        if mathml:
            mathml=mathml[0]
            mathml.set("xmlns","http://www.w3.org/1998/Math/MathML")
            # add annotation with original TeX
            #a = ET.Element("annotation", encoding="TeX")
            #a.text=latex
            #mathml.append(a)
            return mathml
        else:
            log ("an error occured, \n%s\n" % outmsg)
        

if __name__ == '__main__':
    test = "\exp(-\gamma x)"
    print
    print ET.tostring(latex2mathml(test))
    
