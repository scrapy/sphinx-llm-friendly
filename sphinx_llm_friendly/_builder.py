from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from docutils.io import StringOutput
from sphinx.builders import Builder
from sphinx.locale import __
from sphinx.util import logging
from sphinx.util.osutil import ensuredir, os_path

from ._llm import prepare_doctree_for_llm
from ._translator import MarkdownTranslator
from ._writer import MarkdownWriter

if TYPE_CHECKING:
    from collections.abc import Iterator
    from collections.abc import Set as AbstractSet

    from docutils import nodes

logger = logging.getLogger(__name__)


@contextmanager
def _io_handler(file_path: str | Path, log_error: bool = True) -> Iterator[None]:
    try:
        yield
    except OSError as err:
        if log_error:
            logger.warning(__("error accessing file %s: %s"), file_path, err)


def _get_mod_time_if_exists(
    file_path: str | Path, log_error: bool = True
) -> float | None:
    with _io_handler(file_path, log_error):
        return Path(file_path).stat().st_mtime
    return None


class MarkdownBuilder(Builder):
    """Builds a Markdown file for every document."""

    name = "llm_markdown"
    format = "markdown"
    epilog = __("The markdown files are in %(outdir)s.")

    allow_parallel = True
    default_translator_class = MarkdownTranslator

    out_suffix = ".md"
    download_dir = "_downloads"

    heading_level_offset = 0
    current_doc_name: str

    def get_outdated_docs(self) -> Iterator[str]:
        for doc_name in self.env.found_docs:
            if doc_name not in self.env.all_docs:
                yield doc_name
                continue

            source_mtime = _get_mod_time_if_exists(self.env.doc2path(doc_name))
            target_mtime = _get_mod_time_if_exists(
                Path(self.outdir, doc_name + self.out_suffix), log_error=False
            )
            if (
                source_mtime is None
                or target_mtime is None
                or source_mtime > target_mtime
            ):
                yield doc_name

    def get_target_uri(self, docname: str, typ: str | None = None) -> str:
        return f"{docname}{self.out_suffix}"

    def prepare_writing(self, docnames: AbstractSet[str]) -> None:
        self.writer = MarkdownWriter(self)

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        self.current_doc_name = docname
        destination = StringOutput(encoding="utf-8")
        self.writer.write(prepare_doctree_for_llm(doctree), destination)
        out_filename = Path(self.outdir, f"{os_path(docname)}{self.out_suffix}")
        ensuredir(out_filename.parent)

        with _io_handler(out_filename):
            out_filename.write_text(self.writer.output or "", encoding="utf-8")

    def finish(self) -> None:
        for src_file_name, (_, dst_path) in self.env.dlfiles.items():
            source_path = Path(self.srcdir, src_file_name)
            destination = Path(self.outdir, self.download_dir, dst_path)
            ensuredir(destination.parent)
            with _io_handler(source_path):
                shutil.copyfile(source_path, destination)
