from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest import mock

import pytest
from sphinx.cmd.build import main

from sphinx_llm_friendly import _intersphinx, build
from sphinx_llm_friendly._llms_txt import _page_order

if TYPE_CHECKING:
    from pathlib import Path

    from sphinx.environment import BuildEnvironment

DOCS = {
    "index.rst": (
        "Project\n=======\n\nThe *first* paragraph.\n\n"
        ".. toctree::\n\n   guide/page1\n   guide/page2\n   news\n"
    ),
    "guide/page1.rst": "Page 1\n======\n\nSee https://example.com/a.html.\n",
    "guide/page2.rst": "Page 2\n======\n",
    "news.rst": "News\n====\n",
    "orphan.rst": ":orphan:\n\nOrphan\n======\n",
}


def _project(tmp_path: Path, conf: str = "") -> Path:
    source = tmp_path / "source"
    for name, content in DOCS.items():
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        (source / name).write_text(content, encoding="utf-8")
    (source / "conf.py").write_text(
        f'project = "Test Project"\nextensions = ["sphinx_llm_friendly"]\n{conf}',
        encoding="utf-8",
    )
    return source


def _build(source: Path, builder: str) -> Path:
    output = source.parent / builder
    assert main(["-q", "-b", builder, str(source), str(output)]) == 0
    return output


def test_llms_txt(tmp_path: Path) -> None:
    output = _build(_project(tmp_path), "html")
    assert (output / "llms.txt").read_text(encoding="utf-8") == (
        "# Test Project\n\n"
        "> The first paragraph.\n\n"
        "## Docs\n\n"
        "- [Project](index.md)\n"
        "- [Page 1](guide/page1.md)\n"
        "- [Page 2](guide/page2.md)\n"
        "- [News](news.md)\n"
        "- [Orphan](orphan.md)\n"
    )


def test_llms_txt_options(tmp_path: Path) -> None:
    conf = (
        'html_baseurl = "https://example.com/en/latest/"\n'
        'llm_friendly_exclude = ["news.rst", "guide/page2*"]\n'
        'llm_friendly_llms_txt_summary = "Line 1.\\nLine 2."\n'
        "llm_friendly_llms_txt_toctree_only = True\n"
    )
    output = _build(_project(tmp_path, conf), "html")
    assert (output / "llms.txt").read_text(encoding="utf-8") == (
        "# Test Project\n\n"
        "> Line 1.\n> Line 2.\n\n"
        "## Docs\n\n"
        "- [Project](en/latest/index.md)\n"
        "- [Page 1](en/latest/guide/page1.md)\n"
    )


def _env(**kwargs: Any) -> BuildEnvironment:
    env = {"toctree_includes": {}, "dependencies": {}, **kwargs}
    return SimpleNamespace(**env)  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("toctree_only", "expected"),
    [
        (True, ["index", "guide/page1"]),
        (False, ["index", "guide/page1", "guide/page2", "includes/snippet"]),
    ],
)
def test_page_order(toctree_only: bool, expected: list[str]) -> None:
    env = _env(
        all_docs=dict.fromkeys(
            ["index", "guide/page1", "includes/snippet", "guide/page2"]
        ),
        toctree_includes={"index": ["guide/page1"], "guide/page1": []},
    )
    assert _page_order(env, "index", toctree_only) == expected


def test_page_order_dependencies() -> None:
    env = _env(
        all_docs=dict.fromkeys(["index", "guide/page1", "guide/snippet", "other"]),
        toctree_includes={"index": ["guide/page1"]},
        dependencies={"guide/page1": {"guide/snippet"}},
    )
    assert _page_order(env, "index", False) == [
        "index",
        "guide/page1",
        "guide/snippet",
        "other",
    ]


def test_html(tmp_path: Path) -> None:
    output = _build(_project(tmp_path, 'llm_friendly_exclude = ["news.rst"]\n'), "html")
    page1 = (output / "guide" / "page1.html").read_text(encoding="utf-8")
    assert '<link rel="alternate" type="text/markdown" href="page1.md">' in page1
    assert "scrapy-copy-as-markdown" in page1
    news = (output / "news.html").read_text(encoding="utf-8")
    assert 'type="text/markdown"' not in news


@pytest.mark.parametrize("builder", ["llm_markdown", "llm_singlemarkdown"])
def test_exclude(tmp_path: Path, builder: str) -> None:
    conf = 'llm_friendly_exclude = ["guide/*"]\n'
    output = _build(_project(tmp_path, conf), builder)
    content = "".join(file.read_text(encoding="utf-8") for file in output.rglob("*.md"))
    assert "Project" in content
    assert "Page 1" not in content


def test_intersphinx(tmp_path: Path) -> None:
    file = tmp_path / "file.md"
    file.write_text(
        "[a](https://a.example/a/b.html#c) [b](https://b.example/b.html) "
        "[c](https://c.example/c.html)\n",
        encoding="utf-8",
    )
    with mock.patch.object(
        _intersphinx,
        "_supports_markdown",
        lambda url: url == "https://a.example/a/",
    ):
        _intersphinx.rewrite_intersphinx_links(
            [file], {"https://a.example/a/", "https://b.example/"}
        )
    assert file.read_text(encoding="utf-8") == (
        "[a](https://a.example/a/b.md#c) [b](https://b.example/b.html) "
        "[c](https://c.example/c.html)\n"
    )


def test_build(tmp_path: Path) -> None:
    conf = (
        'extensions.append("sphinx.ext.intersphinx")\n'
        'intersphinx_mapping = {"e": ("https://example.com/", "missing.inv")}\n'
    )
    with mock.patch.object(_intersphinx, "_supports_markdown", return_value=True):
        output = build(_project(tmp_path, conf), tmp_path / "build")
    assert output == tmp_path / "build" / "all"
    assert (output / "guide" / "page1.html").exists()
    page1 = (output / "guide" / "page1.md").read_text(encoding="utf-8")
    assert "https://example.com/a.md" in page1
    assert (output / "llms.txt").exists()
    llms_full = (output / "llms-full.txt").read_text(encoding="utf-8")
    assert llms_full.startswith("# Test Project Documentation\n\nSource: /index.md")
