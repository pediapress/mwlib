import importlib.metadata
import os
from pathlib import Path

import toml


def find_pyproject_toml():
    if os.getenv("MWLIB_PYPROJECT_TOML", None):
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
    with open(find_pyproject_toml(), encoding="utf-8") as file:
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
