from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from docutils.io import StringOutput
from sphinx.locale import __
from sphinx.util import logging
from sphinx.util.osutil import ensuredir, os_path

from ._builder import MarkdownBuilder
from ._exclude import is_excluded
from ._llm import prepare_doctree_for_llm
from ._writer import MarkdownWriter

if TYPE_CHECKING:
    from collections.abc import Sequence
    from collections.abc import Set as AbstractSet

    from docutils import nodes

logger = logging.getLogger(__name__)


class SingleFileMarkdownBuilder(MarkdownBuilder):
    """Builds the whole document tree as a single Markdown page."""

    name = "llm_singlemarkdown"
    epilog = __("The Markdown page is in %(outdir)s.")

    copysource = False

    heading_level_offset = 1
    """Keeps the synthetic documentation title as the only H1."""

    def _render_doctree(self, doctree: nodes.document) -> str:
        writer = MarkdownWriter(self)
        writer.write(doctree, StringOutput(encoding="utf-8"))
        return writer.output or ""

    def _ordered_docnames(self, root_doc: str) -> list[str]:
        """Return documents in depth-first toctree order from the root
        document.
        """
        docnames: list[str] = []
        seen: set[str] = set()

        def visit(docname: str) -> None:
            if docname in seen:
                return
            seen.add(docname)
            docnames.append(docname)
            for child in self.env.toctree_includes.get(docname, []):
                visit(child)

        visit(root_doc)
        return docnames

    def get_outdated_docs(self) -> str:  # type: ignore[override]
        return "all documents"

    def get_target_uri(self, docname: str, typ: str | None = None) -> str:
        if docname in self.env.all_docs:
            return f"#{docname}"
        return docname + self.out_suffix

    def get_relative_uri(self, from_: str, to: str, typ: str | None = None) -> str:
        return self.get_target_uri(to, typ)

    def _append_doc_content(self, content_parts: list[str], docname: str) -> None:
        logger.info(f"Adding content from {docname}")
        self.current_doc_name = docname
        try:
            doc = prepare_doctree_for_llm(self.env.get_doctree(docname))
            rendered = self._render_doctree(doc)
            if not rendered.strip():
                return
            content_parts.append(f"Source: /{docname}{self.out_suffix}\n\n")
            content_parts.append(rendered)
            content_parts.append("\n\n")
        except Exception as e:
            logger.warning(f"Error adding content from {docname}: {e}")

    def _write_single_markdown(self) -> None:
        root_doc = self.config.root_doc
        content_parts = [f"# {self.config.project} Documentation\n\n"]
        exclude = self.config.llm_friendly_llms_full_txt_exclude
        for docname in self._ordered_docnames(root_doc):
            if not is_excluded(self.app, docname, exclude):
                self._append_doc_content(content_parts, docname)

        content = "".join(content_parts)
        # Normalize whitespace while keeping paragraph breaks intact.
        content = re.sub(r"[ \t]+\n", "\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = content.strip() + "\n"

        outfilename = Path(self.outdir, os_path(root_doc) + self.out_suffix)
        ensuredir(outfilename.parent)
        try:
            outfilename.write_text(content, encoding="utf-8")
        except OSError as err:
            logger.warning(__("error writing file %s: %s"), outfilename, err)

    # Sphinx 8+
    def write_documents(self, _docnames: AbstractSet[str]) -> None:
        self._write_single_markdown()

    # Sphinx 7
    def _write_serial(self, _docnames: Sequence[str]) -> None:
        self._write_single_markdown()

    def _write_parallel(self, _docnames: Sequence[str], _nproc: int) -> None:
        self._write_single_markdown()
