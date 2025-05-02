"""
converts LaTex to Mathml using blahtexml

FIXME: Robustness, error handling, ....
# see integration in MW:
http://cvs.berlios.de/cgi-bin/viewcvs.cgi/blahtex/blahtex/includes/Math.php?rev=HEAD&content-type=text/vnd.viewcvs-markup

FIXME: replace with texvc which is deistributed with MediaWiki


"""


import subprocess
import sys

try:
    import xml.etree.ElementTree as ET
except BaseException:
    from elementtree import ElementTree as ET
from xml.parsers.expat import ExpatError


def log(err):
    sys.stderr.write(err + " ")


def latex2mathml(latex):
    data = f"\\displaystyle\n{latex.strip()}\n"
    with subprocess.Popen(
        ["blahtexml", "--mathml"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as popen:
        popen.stdin.write(data)
        output, errors = popen.communicate()

    if output:
        # ET has unreadable namespace handling
        # http://effbot.org/zone/element.htm#xml-namespaces
        # ET._namespace_map["http://www.w3.org/1998/Math/MathML"] = 'mathml'
        # remove xmlns declaration
        # outmsg = outmsg.replace('xmlns="http://www.w3.org/1998/Math/MathML"', '')

        output = '<?xml version="1.0" encoding="UTF-8"?>\n' + output

        try:
            tree = ET.fromstring(output)
        except ExpatError:
            log("\n\nparsing failed\n\n")
            log(latex + "\n\n")
            log(data + "\n\n")
            log(errors + "\n")
            log(output + "\n")
            return None

        tag = "mathml"
        mathml = tree.iter(tag)

        if mathml:
            mathml = mathml.next()
            mathml.set("xmlns", "http://www.w3.org/1998/Math/MathML")
            return mathml
        log(f"an error occured, \n{output}\n")
    return None


if __name__ == "__main__":
    TEST = r"\exp(-\gamma x)"
    print()
    print(ET.tostring(latex2mathml(TEST)))
