from pathlib import Path
import tomllib


def test_project_declares_build_backend_for_console_scripts():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["mem"] == "memisalluneed.cli:main"
    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"


def test_ui_static_assets_are_included_as_package_data():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "ui_static/*" in pyproject["tool"]["setuptools"]["package-data"][
        "memisalluneed"
    ]
