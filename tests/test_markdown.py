from __future__ import annotations

import shutil
import stat
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sphinx
from sphinx.cmd.build import main

if TYPE_CHECKING:
    from collections.abc import Callable

SOURCE_PATH = Path(__file__).parent / "source"
EXPECTED_PATH = Path(__file__).parent / "expected"


def run_sphinx(builder: str, build_path: Path, *flags: str) -> None:
    assert main(["-b", builder, str(SOURCE_PATH), str(build_path), *flags]) == 0


def _markdown_files(path: Path) -> dict[str, str]:
    return {
        file.relative_to(path).as_posix(): file.read_text(encoding="utf-8")
        for file in path.rglob("*.md")
        if "_downloads" not in file.parts
    }


def _chmod_output(build_path: Path, apply_func: Callable[[int], int]) -> None:
    for file in build_path.rglob("*.md"):
        file.chmod(apply_func(file.stat().st_mode))


@pytest.mark.skipif(
    sphinx.version_info < (9,), reason="Sphinx 9 changed the toctree of index.md"
)
def test_markdown_expected_output(tmp_path: Path) -> None:
    run_sphinx("llm_markdown", tmp_path, "-t", "Partners")
    assert _markdown_files(tmp_path) == _markdown_files(EXPECTED_PATH / "llm_markdown")


def test_singlemarkdown_expected_output(tmp_path: Path) -> None:
    run_sphinx("llm_singlemarkdown", tmp_path, "-t", "Partners")
    actual = (tmp_path / "index.md").read_text(encoding="utf-8")
    assert actual == (EXPECTED_PATH / "llms-full.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("builder", ["llm_markdown", "llm_singlemarkdown"])
def test_rebuild(builder: str, tmp_path: Path) -> None:
    run_sphinx(builder, tmp_path)
    (SOURCE_PATH / "index.rst").touch()
    run_sphinx(builder, tmp_path)
    shutil.rmtree(tmp_path)
    run_sphinx(builder, tmp_path)
    assert (tmp_path / "index.md").exists()


@pytest.mark.parametrize("builder", ["llm_markdown", "llm_singlemarkdown"])
def test_read_only_output(builder: str, tmp_path: Path) -> None:
    run_sphinx(builder, tmp_path)
    (SOURCE_PATH / "index.rst").touch()
    flag = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    _chmod_output(tmp_path, lambda mode: mode & ~flag)
    try:
        run_sphinx(builder, tmp_path)
    finally:
        _chmod_output(tmp_path, lambda mode: mode | flag)


def test_download_references(tmp_path: Path) -> None:
    source_path = tmp_path / "source"
    nested_path = source_path / "guide"
    assets_path = source_path / "assets"
    output_path = tmp_path / "output"
    nested_path.mkdir(parents=True)
    assets_path.mkdir()

    (source_path / "conf.py").write_text(
        'extensions = ["sphinx_llm_friendly"]\n', encoding="utf-8"
    )
    (source_path / "index.rst").write_text(
        ".. toctree::\n\n   guide/downloads\n", encoding="utf-8"
    )
    (nested_path / "downloads.rst").write_text(
        "Downloads\n"
        "=========\n\n"
        "Download :download:`sample <../assets/sample.pdf>`.\n\n"
        "Visit :download:`external <https://example.com/sample.pdf>`.\n",
        encoding="utf-8",
    )
    sample_contents = b"sample download contents"
    (assets_path / "sample.pdf").write_bytes(sample_contents)

    assert main(["-b", "llm_markdown", str(source_path), str(output_path)]) == 0

    downloads = list((output_path / "_downloads").glob("*/sample.pdf"))
    assert len(downloads) == 1
    assert downloads[0].read_bytes() == sample_contents

    markdown = (output_path / "guide" / "downloads.md").read_text(encoding="utf-8")
    download_uri = downloads[0].relative_to(output_path).as_posix()
    assert f"](../{download_uri})" in markdown
    assert "](../assets/sample.pdf)" not in markdown
    assert "](https://example.com/sample.pdf)" in markdown
