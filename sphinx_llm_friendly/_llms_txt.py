from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from docutils import nodes

from ._exclude import is_excluded

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.config import Config
    from sphinx.environment import BuildEnvironment


def docs_path_prefix(config: Config) -> str:
    """Return the path of ``html_baseurl`` as a prefix for links to
    documents, e.g. ``/en/latest/``, or an empty string if it has no path.
    """
    docs_path = urlsplit(config.html_baseurl).path.strip("/")
    return f"/{docs_path}/" if docs_path else ""


def _page_order(env: BuildEnvironment, root_doc: str, toctree_only: bool) -> list[str]:
    page_order: list[str] = []
    visited: set[str] = set()

    def collect(docname: str) -> None:
        if docname in visited:
            return
        visited.add(docname)
        page_order.append(docname)
        if children := env.toctree_includes.get(docname, []):
            for child in children:
                collect(child)
        elif toctree_only:
            return
        elif docname in env.dependencies:
            for dependency in env.dependencies[docname]:
                if dependency in env.all_docs:
                    collect(str(dependency))
        elif prefix := "/".join(docname.split("/")[:-1]):
            # Documents in the same directory might be related.
            for other in list(env.all_docs):
                if other.startswith(prefix) and other != docname:
                    collect(other)

    collect(root_doc)
    if not toctree_only:
        page_order.extend(sorted(set(env.all_docs) - visited))
    return page_order


def _root_first_paragraph(env: BuildEnvironment, root_doc: str) -> str:
    for paragraph in env.get_doctree(root_doc).findall(nodes.paragraph):
        if text := paragraph.astext():
            return text
    return ""


def _title(env: BuildEnvironment, docname: str) -> str:
    title = env.titles.get(docname)
    return (title.astext() if title else "") or docname


def write_llms_txt(app: Sphinx) -> None:
    config = app.config
    env = app.env
    root_doc = config.root_doc

    summary = config.llm_friendly_llms_txt_summary
    if summary is None:
        summary = _root_first_paragraph(env, root_doc)
    prefix = docs_path_prefix(config)

    lines = [f"# {config.project}\n\n"]
    if summary := summary.strip():
        summary = summary.replace("\n", "\n> ")
        lines.append(f"> {summary}\n\n")
    lines.append("## Docs\n\n")
    lines.extend(
        f"- [{_title(env, docname)}]({prefix}{docname}.md)\n"
        for docname in _page_order(
            env, root_doc, config.llm_friendly_llms_txt_toctree_only
        )
        if not is_excluded(env, docname)
    )
    Path(app.outdir, "llms.txt").write_text("".join(lines), encoding="utf-8")
