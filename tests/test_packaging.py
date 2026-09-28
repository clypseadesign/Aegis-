"""Guards for packaging correctness.

The wheel is what ships inside the container, and setuptools' package discovery
is easy to break silently: a missing `include` or `package-data` entry omits
modules and the bundled YAML library without any build-time error. The failure
only appears at runtime as `ModuleNotFoundError: No module named 'app.cli'`.
"""

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from app.services.seed_tests import DEFAULT_TEST_CASE_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def test_cli_package_exists() -> None:
    assert (REPO_ROOT / "backend/app/cli/__init__.py").is_file()
    assert (REPO_ROOT / "backend/app/cli/seed_tests.py").is_file()


def test_bundled_test_cases_are_package_data() -> None:
    """test_cases/ holds YAML, which packaging must include explicitly."""
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"].get("package-data", {})
    patterns = package_data.get("app", [])
    assert patterns, "package-data must declare app.test_cases"
    assert any("test_cases" in pattern for pattern in patterns)


def test_packages_find_has_explicit_include() -> None:
    """Auto-discovery drops packages; an explicit include prevents that."""
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    find = config["tool"]["setuptools"]["packages"]["find"]
    assert find.get("include"), "packages.find needs an explicit include list"


def test_default_dir_resolves_inside_installed_package() -> None:
    """The seeder must find the library relative to the package, not the CWD."""
    assert DEFAULT_TEST_CASE_DIR.is_absolute()
    assert DEFAULT_TEST_CASE_DIR.is_dir()
    assert (DEFAULT_TEST_CASE_DIR / "prompt_injection").is_dir()


@pytest.mark.slow
def test_wheel_ships_cli_and_test_cases(tmp_path: Path) -> None:
    """Build a wheel and assert the CLI and YAML library are inside it.

    Skipped unless explicitly requested, since it needs the build backend and
    network access. Run with: pytest -m slow
    """

    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"wheel build unavailable: {result.stderr[-200:]}")

    import zipfile

    wheels = list(tmp_path.glob("*.whl"))
    assert wheels, "no wheel produced"
    names = zipfile.ZipFile(wheels[0]).namelist()

    assert "app/cli/seed_tests.py" in names, "CLI missing from wheel"
    assert "app/services/seed_tests.py" in names, "seeding service missing from wheel"

    yaml_count = sum(1 for name in names if name.endswith(".yaml"))
    assert yaml_count >= 50, f"only {yaml_count} YAML test cases shipped"
