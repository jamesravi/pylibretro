import toml
from pathlib import Path
import pylibretro

def test_versions_are_in_sync():
    """
    Checks if the pyproject.toml and package.__init__.py __version__ are in sync.
    Adapted from https://github.com/python-poetry/poetry/issues/144#issuecomment-877835259
    Possible alternative that I could implement in the future could be
    https://github.com/python-poetry/poetry/pull/2366#issuecomment-652418094
    """

    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = toml.loads(open(str(path)).read())
    pyproject_version = pyproject["tool"]["poetry"]["version"]

    package_init_version = pylibretro.__version__

    assert package_init_version == pyproject_version
