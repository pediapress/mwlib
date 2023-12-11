#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


import os
import shutil
import tempfile
from subprocess import PIPE, Popen

import six

try:
    import xml.etree.ElementTree as ET
except BaseException:
    from elementtree import ElementTree as ET

from mwlib.utilities import log

log = log.Log("mwlib.mathutils")


def try_system(cmd):
    dev_null_path = os.path.devnull
    cmd += f" >{dev_null_path} 2>{dev_null_path}"
    return os.system(cmd)


texvc_available = not try_system("texvc")
blahtexml_available = not try_system("blahtexml")


def _extract_output_from_parsed_xml(result, output_path, output_mode):
    parsed_tree = ET.fromstring(result)
    if output_mode == "png":
        png_elements = parsed_tree.iter("png")
        if png_elements:
            png_fn = png_elements.next().findtext("md5")
            if png_fn:
                png_fn = os.path.join(output_path, png_fn + ".png")
                if os.path.exists(png_fn):
                    return png_fn
    elif output_mode == "mathml":
        mathml = parsed_tree.iter("mathml")
        if mathml:
            mathml = mathml.next()
            mathml.set("xmlns", "http://www.w3.org/1998/Math/MathML")
            return mathml
    return None


def _render_math_blahtex(latex, output_path, output_mode):
    if not blahtexml_available:
        return None
    cmd = ["blahtexml", "--texvc-compatible-commands"]
    if output_mode == "mathml":
        cmd.append("--mathml")
    elif output_mode == "png":
        cmd.append("--png")
    else:
        return None

    if output_path:
        try:  # for some reason os.getcwd failed at some point. this should be investigated...
            curdir = os.getcwd()
        except BaseException:
            curdir = None
        os.chdir(output_path)
    latex = latex.lstrip()
    if not latex:
        return None

    try:
        sub = Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE)
    except OSError:
        log.error("error with blahtexml. cmd:", repr(" ".join(cmd)))
        if curdir:
            os.chdir(curdir)
        return None

    (result, _) = sub.communicate(latex.encode("utf-8"))
    del sub

    if curdir is not None:
        os.chdir(curdir)
    if result:
        output = _extract_output_from_parsed_xml(result, output_path, output_mode)
        if output:
            return output
    log.error(
        f"error converting math (blahtexml). source: {latex!r} \nerror: {result!r}"
    )
    return None


def _render_math_texvc(latex, output_path, output_mode="png", resolution_in_dpi=120):
    """only render mode is png"""
    if not texvc_available:
        return None
    cmd = [
        "texvc",
        output_path,
        output_path,
        latex.encode("utf-8"),
        "UTF-8",
        str(resolution_in_dpi),
    ]
    try:
        sub = Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE)
    except OSError:
        log.error("error with texvc. cmd:", repr(" ".join(cmd)))
        return None
    (result, error) = sub.communicate()
    del sub

    if output_mode == "png" and len(result) >= 32:
        png_fn = os.path.join(output_path, result[1:33] + ".png")
        if os.path.exists(png_fn):
            return png_fn

    log.error(f"error converting math (texvc). source: {latex!r} \nerror: {result!r}")
    return None


def render_math(
    latex,
    output_path=None,
    output_mode="png",
    render_engine="blahtexml",
    resolution_in_dpi=120,
):
    """
    @param latex: LaTeX code
    @type latex: unicode

    @param output_mode: one of the values 'png' or 'mathml'. mathml only works
        with blahtexml as render_engine
    @type output_mode: str

    @param render_engine: one of the value 'blahtexml' or 'texvc'
    @type render_engine: str

    @returns: either path to generated png or mathml string
    @rtype: str
    """
    if not latex:
        return
    if output_mode not in ("png", "mathml"):
        raise ValueError("output_mode must be one of 'png' or 'mathml'")
    if render_engine not in ("blahtexml", "texvc"):
        raise ValueError("render_engine must be one of 'blahtexml' or 'texvc'")
    if not isinstance(latex, six.text_type):
        raise TypeError("latex must be of type unicode")

    if output_mode == "png" and not output_path:
        log.error("math rendering with output_mode png requires an output_path")
        raise ValueError("output path required")

    remove_tmp_dir = False
    if output_mode == "mathml" and not output_path:
        output_path = tempfile.mkdtemp()
        remove_tmp_dir = True
    output_path = os.path.abspath(output_path)
    result = None

    if render_engine == "blahtexml":
        result = _render_math_blahtex(
            latex, output_path=output_path, output_mode=output_mode
        )
    if result is None and output_mode == "png":
        result = _render_math_texvc(
            latex,
            output_path=output_path,
            output_mode=output_mode,
            resolution_in_dpi=resolution_in_dpi,
        )

    if remove_tmp_dir:
        shutil.rmtree(output_path)
    return result


if __name__ == "__main__":
    LATEX = "\\sqrt{4}=2"

    print(render_math(LATEX, output_mode="mathml"))
    print(render_math(LATEX, output_path="/tmp/", output_mode="png"))
    print(
        render_math(
            LATEX, output_path="/tmp/", output_mode="png", render_engine="texvc"
        )
    )
