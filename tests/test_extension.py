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
    "guide/page1.rst": (
        "Page 1\n======\n\n"
        "See https://example.com/guide/page2.html#page-2,\n"
        "https://example.com/_static/file.html and https://example.com/b/news.html.\n"
    ),
    "guide/page2.rst": (
        "Page 2\n======\n\nSee :doc:`page1` and :doc:`/news`.\n\n"
        ".. container:: llm-friendly-exclude\n\n   Hidden.\n"
    ),
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


def test_markdown(tmp_path: Path) -> None:
    conf = 'llm_friendly_exclude = ["news.rst"]\n'
    output = _build(_project(tmp_path, conf), "html")
    page2 = (output / "guide" / "page2.md").read_text(encoding="utf-8")
    assert "See [Page 1](page1.md) and [News](../news.html)." in page2
    assert "Hidden" not in page2
    assert "Hidden" in (output / "guide" / "page2.html").read_text(encoding="utf-8")
    assert not (output / "news.md").exists()
    llms_full = (output / "llms-full.txt").read_text(encoding="utf-8")
    assert "Source: /guide/page2.md" in llms_full
    assert "Source: /news.md" not in llms_full


def test_sphinx_design(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _project(tmp_path, 'extensions.append("sphinx_design")\n')
    (source / "news.rst").write_text(
        "News\n====\n\n"
        ".. dropdown:: Title\n\n   Dropdown.\n\n"
        ".. dropdown::\n\n   Untitled.\n\n"
        ".. tab-set::\n\n"
        "   .. tab-item:: Tab 1\n\n      One.\n\n"
        "   .. tab-item:: Tab 2\n\n      Two.\n\n"
        ".. meta::\n   :description: Meta.\n\n"
        ".. button-ref:: guide/page1\n",
        encoding="utf-8",
    )
    output = _build(source, "html")
    assert (output / "news.md").read_text(encoding="utf-8") == (
        "# News\n\n### Title\n\nDropdown.\n\nUntitled.\n\n"
        "### Tab 1\n\nOne.\n\n### Tab 2\n\nTwo.\n\n[Page 1](guide/page1.md)\n"
    )
    assert "unknown node type" not in capsys.readouterr().err


def test_sphinx_design_excluded_tabs(tmp_path: Path) -> None:
    source = _project(tmp_path, 'extensions.append("sphinx_design")\n')
    (source / "news.rst").write_text(
        "News\n====\n\n"
        ".. tab-set::\n\n"
        "   .. tab-item:: Tab 1\n      :class-label: llm-friendly-exclude\n\n"
        "      One.\n\n"
        "   .. tab-item:: Tab 2\n\n      Two.\n\n"
        ".. tab-set::\n\n"
        "   .. tab-item:: Tab 3\n      :class-content: llm-friendly-exclude\n\n"
        "      Three.\n",
        encoding="utf-8",
    )
    output = _build(source, "html")
    assert (output / "news.md").read_text(encoding="utf-8") == (
        "# News\n\n### Tab 2\n\nTwo.\n"
    )
    html = (output / "news.html").read_text(encoding="utf-8")
    assert "Tab 1" in html
    assert "Three." in html


@pytest.mark.parametrize(("max_tokens", "warns"), [(1, True), (None, False)])
def test_llms_full_txt_max_tokens(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    max_tokens: int | None,
    warns: bool,
) -> None:
    conf = f"llm_friendly_llms_full_txt_max_tokens = {max_tokens}\n"
    output = _build(_project(tmp_path, conf), "html")
    assert (output / "llms-full.txt").exists()
    assert (
        "over the llm_friendly_llms_full_txt_max_tokens limit of 1."
        in capsys.readouterr().err
    ) is warns


def test_only(tmp_path: Path) -> None:
    source = _project(tmp_path)
    (source / "news.rst").write_text(
        "News\n====\n\n"
        ".. only:: not llm\n\n   HTML.\n\n"
        ".. only:: llm\n\n   Markdown.\n\n"
        ".. only:: html or llm\n\n   Both.\n",
        encoding="utf-8",
    )
    output = _build(source, "html")
    assert (output / "news.md").read_text(encoding="utf-8") == (
        "# News\n\nMarkdown.\n\nBoth.\n"
    )
    html = (output / "news.html").read_text(encoding="utf-8")
    assert "HTML." in html
    assert "Markdown." not in html
    assert "Both." in html
    assert "markdown" not in (output / "searchindex.js").read_text(encoding="utf-8")


def test_llms_full_txt_exclude(tmp_path: Path) -> None:
    conf = 'llm_friendly_llms_full_txt_exclude = ["guide/page1*"]\n'
    output = _build(_project(tmp_path, conf), "html")
    llms_full = (output / "llms-full.txt").read_text(encoding="utf-8")
    assert "Source: /index.md" in llms_full
    assert "Source: /guide/page1.md" not in llms_full
    assert (output / "guide" / "page1.md").exists()
    assert "guide/page1.md" in (output / "llms.txt").read_text(encoding="utf-8")


def test_intersphinx(tmp_path: Path) -> None:
    inventory = _build(_project(tmp_path / "remote"), "html") / "objects.inv"
    conf = (
        'extensions.append("sphinx.ext.intersphinx")\n'
        "intersphinx_mapping = {\n"
        f'    "a": ("https://example.com/", "{inventory}"),\n'
        f'    "b": ("https://example.com/b/", "{inventory}"),\n'
        "}\n"
    )
    with mock.patch.object(
        _intersphinx,
        "_supports_markdown",
        lambda url: url == "https://example.com/",
    ):
        output = _build(_project(tmp_path, conf), "html")
    page1 = (output / "guide" / "page1.md").read_text(encoding="utf-8")
    assert "(https://example.com/guide/page2.md#page-2)" in page1
    assert "(https://example.com/_static/file.html)" in page1
    assert "(https://example.com/b/news.html)" in page1


def test_build(tmp_path: Path) -> None:
    with pytest.warns(DeprecationWarning):
        output = build(_project(tmp_path), tmp_path / "build")
    assert output == tmp_path / "build" / "all"
    assert (output / "guide" / "page1.md").exists()
    assert (output / "llms-full.txt").exists()
