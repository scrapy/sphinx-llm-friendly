from __future__ import annotations

import re
from pathlib import Path
from types import MethodType
from typing import TYPE_CHECKING

import tiktoken
from sphinx.util import logging

from ._exclude import is_excluded
from ._llm import prepare_doctree_for_llm
from ._llms_txt import docs_path_prefix
from ._translator import MarkdownTranslator

if TYPE_CHECKING:
    from docutils import nodes
    from sphinx.application import Sphinx
    from sphinx.builders.html import StandaloneHTMLBuilder
    from sphinx.environment import BuildEnvironment

logger = logging.getLogger(__name__)


def _render(app: Sphinx, doctree: nodes.document, single_file: bool = False) -> str:
    builder: StandaloneHTMLBuilder = app.builder  # type: ignore[assignment]
    translator = MarkdownTranslator(doctree, builder, single_file)
    handlers = app.registry.translation_handlers.get("llm_markdown", {})
    for name, (visit, depart) in handlers.items():
        setattr(translator, f"visit_{name}", MethodType(visit, translator))
        if depart:
            setattr(translator, f"depart_{name}", MethodType(depart, translator))
    doctree.walkabout(translator)
    return translator.astext()


def _fragment_path(app: Sphinx, docname: str) -> Path:
    return Path(app.doctreedir, "llm_friendly", f"{docname}.md")


def write_markdown(app: Sphinx, docname: str, doctree: nodes.document) -> None:
    """Write the Markdown version of *docname* next to its HTML version, and
    its ``llms-full.txt`` fragment into the doctree directory.
    """
    doctree = prepare_doctree_for_llm(doctree)
    page = Path(app.outdir, f"{docname}.md")
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_render(app, doctree), encoding="utf-8")
    fragment = _fragment_path(app, docname)
    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.write_text(_render(app, doctree, single_file=True), encoding="utf-8")


def _ordered_docnames(env: BuildEnvironment, root_doc: str) -> list[str]:
    docnames: dict[str, None] = {}

    def visit(docname: str) -> None:
        if docname in docnames:
            return
        docnames[docname] = None
        for child in env.toctree_includes.get(docname, []):
            visit(child)

    visit(root_doc)
    return list(docnames)


def write_llms_full_txt(app: Sphinx) -> None:
    """Join the ``llms-full.txt`` fragments of the documents reachable from
    the root document, in toctree order.
    """
    env = app.env
    content_parts = [f"# {app.config.project} Documentation\n\n"]
    prefix = docs_path_prefix(app.config) or "/"
    for docname in _ordered_docnames(env, app.config.root_doc):
        if is_excluded(env, docname) or is_excluded(
            env, docname, app.config.llm_friendly_llms_full_txt_exclude
        ):
            continue
        rendered = _fragment_path(app, docname).read_text(encoding="utf-8")
        if rendered.strip():
            content_parts.append(f"Source: {prefix}{docname}.md\n\n{rendered}\n\n")

    content = "".join(content_parts)
    # Normalize whitespace while keeping paragraph breaks intact.
    content = re.sub(r"[ \t]+\n", "\n", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = content.strip() + "\n"
    path = Path(app.outdir, "llms-full.txt")
    path.write_text(content, encoding="utf-8")

    max_tokens = app.config.llm_friendly_llms_full_txt_max_tokens
    if max_tokens is None:
        return
    tokens = len(tiktoken.get_encoding("cl100k_base").encode(content))
    if tokens > max_tokens:
        logger.warning(
            f"{path} has {tokens:,} tokens, over the "
            f"llm_friendly_llms_full_txt_max_tokens limit of {max_tokens:,}.",
            type="llm_friendly",
            subtype="max_tokens",
        )
