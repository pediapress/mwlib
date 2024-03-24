import importlib.metadata
import logging
import os
from pathlib import Path

import toml

logger = logging.getLogger(__name__)


def find_pyproject_toml():
    MWLIB_PYPROJECT_TOML = os.getenv("MWLIB_PYPROJECT_TOML", "")
    if MWLIB_PYPROJECT_TOML:
        return Path(os.getenv("MWLIB_PYPROJECT_TOML")).resolve()

    current_dir = Path(__file__).resolve().parent

    # Check until we reach the root folder
    while current_dir != current_dir.parent:
        candidate = current_dir / "pyproject.toml"
        if candidate.exists():
            return candidate

        current_dir = current_dir.parent

    return None


def get_version_from_pyproject():
    pyproject_toml_path = find_pyproject_toml()
    if not pyproject_toml_path:
        logger.warning("pyproject.toml not found")
        return "0.0.0"
    with open(pyproject_toml_path, encoding="utf-8") as file:
        pyproject_data = toml.load(file)
        ver = pyproject_data["project"]["version"]
        return ver


def get_version_from_package(package_name):
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


version = get_version_from_pyproject()
__version_info__ = tuple(map(int, version.split(".")))
display_version = __version__ = version


def main():
    for mwlib_package in ("mwlib", "mwlib.rl", "mwlib.ext", "mwlib.hiq"):
        ver = get_version_from_package(mwlib_package)
        if ver:
            print(mwlib_package, ver)


if __name__ == "__main__":
    main()
