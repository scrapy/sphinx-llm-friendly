from __future__ import annotations

from pathlib import Path

import pytest
import sphinx
from sphinx.cmd.build import main

SOURCE_PATH = Path(__file__).parent / "source"
EXPECTED_PATH = Path(__file__).parent / "expected"


def run_sphinx(build_path: Path, *flags: str) -> None:
    assert main(["-b", "html", str(SOURCE_PATH), str(build_path), *flags]) == 0


def _markdown_files(path: Path) -> dict[str, str]:
    return {
        file.relative_to(path).as_posix(): file.read_text(encoding="utf-8")
        for file in path.rglob("*.md")
        if not {"_downloads", ".doctrees"} & set(file.parts)
    }


@pytest.mark.skipif(
    sphinx.version_info < (9,), reason="Sphinx 9 changed the toctree of index.md"
)
def test_markdown_expected_output(tmp_path: Path) -> None:
    run_sphinx(tmp_path, "-t", "Partners")
    assert _markdown_files(tmp_path) == _markdown_files(EXPECTED_PATH / "llm_markdown")


def test_llms_full_txt_expected_output(tmp_path: Path) -> None:
    run_sphinx(tmp_path, "-t", "Partners")
    actual = (tmp_path / "llms-full.txt").read_text(encoding="utf-8")
    assert actual == (EXPECTED_PATH / "llms-full.txt").read_text(encoding="utf-8")


def test_rebuild(tmp_path: Path) -> None:
    run_sphinx(tmp_path, "-t", "Partners")
    (tmp_path / "blocks.md").unlink()
    (SOURCE_PATH / "index.rst").touch()
    run_sphinx(tmp_path, "-t", "Partners")
    assert not (tmp_path / "blocks.md").exists()
    actual = (tmp_path / "llms-full.txt").read_text(encoding="utf-8")
    assert actual == (EXPECTED_PATH / "llms-full.txt").read_text(encoding="utf-8")


def test_parallel(tmp_path: Path) -> None:
    run_sphinx(tmp_path, "-t", "Partners", "-j", "2")
    actual = (tmp_path / "llms-full.txt").read_text(encoding="utf-8")
    assert actual == (EXPECTED_PATH / "llms-full.txt").read_text(encoding="utf-8")


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

    assert main(["-b", "html", str(source_path), str(output_path)]) == 0

    downloads = list((output_path / "_downloads").glob("*/sample.pdf"))
    assert len(downloads) == 1
    assert downloads[0].read_bytes() == sample_contents

    markdown = (output_path / "guide" / "downloads.md").read_text(encoding="utf-8")
    download_uri = downloads[0].relative_to(output_path).as_posix()
    assert f"](../{download_uri})" in markdown
    assert "](../assets/sample.pdf)" not in markdown
    assert "](https://example.com/sample.pdf)" in markdown
