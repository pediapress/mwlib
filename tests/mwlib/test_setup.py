import importlib.util
from pathlib import Path

import toml
from setuptools import Extension

root_dir = Path(__file__).resolve().parent.parent.parent

# Import setup.py as a module
spec = importlib.util.spec_from_file_location("setup", root_dir / "setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

# Import functions and constants from setup.py
get_version = setup.get_version
get_ext_modules = setup.get_ext_modules
MWLIB_SRC_DIR = root_dir / setup.MWLIB_SRC_DIR


def test_get_version():
    with open(root_dir / "pyproject.toml") as f:
        pyproject = toml.load(f)
        expected_version = pyproject["project"]["version"]

    # Call get_version() and assert that it returns the expected version number
    assert get_version() == expected_version


def test_get_ext_modules():
    expected_extensions = [
        Extension("mwlib.parser.refine._core", sources=[f"{MWLIB_SRC_DIR}/parser/refine/_core.pyx"]),
        Extension("mwlib.parser.templ.evaluate", sources=[f"{MWLIB_SRC_DIR}/parser/templ/evaluate.pyx"]),
        Extension("mwlib.parser.templ.node", sources=[f"{MWLIB_SRC_DIR}/parser/templ/node.pyx"]),
        Extension("mwlib.parser.templ.nodes", sources=[f"{MWLIB_SRC_DIR}/parser/templ/nodes.pyx"]),
        Extension("mwlib.parser.token._uscan", sources=[f"{MWLIB_SRC_DIR}/parser/token/_uscan.cc"]),
    ]

    # Patch the MWLIB_SRC_DIR in the setup module
    setup.MWLIB_SRC_DIR = str(MWLIB_SRC_DIR)

    extensions = get_ext_modules()
    extensions.sort(key=lambda e: e.name)

    assert len(extensions) == len(expected_extensions)

    for expected_ext, ext in zip(expected_extensions, extensions, strict=False):
        assert expected_ext.name == ext.name
        assert expected_ext.sources == ext.sources
