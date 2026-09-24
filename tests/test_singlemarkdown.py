from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from docutils import nodes
from docutils.utils import new_document
from sphinx.environment import BuildEnvironment

from sphinx_llm_friendly._singlemarkdown import SingleFileMarkdownBuilder

if TYPE_CHECKING:
    from pathlib import Path


def _make_builder(
    tmp_path: Path, all_docs: set[str]
) -> tuple[SingleFileMarkdownBuilder, mock.MagicMock]:
    app = mock.MagicMock()
    app.doctreedir = str(tmp_path / "doctree")
    app.config.root_doc = "index"
    app.config.project = "Test Project"
    env = mock.MagicMock(spec=BuildEnvironment)
    env.all_docs = dict.fromkeys(all_docs)
    env.found_docs = all_docs
    env.toctree_includes = {}
    builder = SingleFileMarkdownBuilder(app, env)
    builder.outdir = tmp_path
    builder._render_doctree = lambda doctree: doctree.astext()  # type: ignore[method-assign]
    return builder, env


def _paragraph_document(text: str) -> nodes.document:
    document = new_document("test")
    document.append(nodes.paragraph("", text))
    return document


def test_uris(tmp_path: Path) -> None:
    builder, _ = _make_builder(tmp_path, {"index", "target"})
    assert builder.get_outdated_docs() == "all documents"
    assert builder.get_target_uri("index") == "#index"
    assert builder.get_target_uri("external") == "external.md"
    assert builder.get_relative_uri("source", "target") == "#target"


def test_toctree_order(tmp_path: Path) -> None:
    builder, env = _make_builder(
        tmp_path, {"index", "z-last", "a-first", "mid", "orphan"}
    )
    env.toctree_includes = {"index": ["mid", "a-first"], "mid": ["z-last"]}
    env.get_doctree.side_effect = _paragraph_document

    builder.write_documents(set())

    assert (tmp_path / "index.md").read_text(encoding="utf-8") == (
        "# Test Project Documentation\n\n"
        "Source: /index.md\n\nindex\n\n"
        "Source: /mid.md\n\nmid\n\n"
        "Source: /z-last.md\n\nz-last\n\n"
        "Source: /a-first.md\n\na-first\n"
    )


def test_document_error(tmp_path: Path) -> None:
    builder, env = _make_builder(tmp_path, {"index", "page1"})
    env.toctree_includes = {"index": ["page1"]}

    def get_doctree(docname: str) -> nodes.document:
        if docname == "index":
            raise ValueError("Test exception")
        return _paragraph_document(docname)

    env.get_doctree.side_effect = get_doctree

    with mock.patch("sphinx_llm_friendly._singlemarkdown.logger") as logger:
        builder.write_documents(set())

    logger.warning.assert_called_once_with(
        "Error adding content from index: Test exception"
    )
    assert (tmp_path / "index.md").read_text(encoding="utf-8") == (
        "# Test Project Documentation\n\nSource: /page1.md\n\npage1\n"
    )
