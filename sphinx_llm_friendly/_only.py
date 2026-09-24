from __future__ import annotations

from typing import TYPE_CHECKING, Any

from docutils import nodes
from sphinx import addnodes
from sphinx.transforms.post_transforms import SphinxPostTransform
from sphinx.util.tags import Tags

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.writers.html5 import HTML5Translator

_HTML_TAGS = frozenset({"html", "format_html", "builder_html"})


class html_only(nodes.General, nodes.Element):
    """Content of an ``only`` directive that applies to the HTML output
    only."""


# A comment, so that the HTML search index skips it.
class markdown_only(nodes.comment):
    """Content of an ``only`` directive that applies to the Markdown output
    only."""


class _SplitOnlyNodes(SphinxPostTransform):
    """Evaluate ``only`` expressions for the Markdown output with the ``llm``
    tag instead of the ``html`` ones, and keep content whose expression
    evaluates differently for HTML and Markdown in only one of them."""

    # Before OnlyNodeTransform.
    default_priority = 49
    formats = ("html",)

    def run(self, **kwargs: Any) -> None:
        tags = getattr(self.env, "_tags", None) or self.app.tags
        markdown_tags = Tags((set(tags) - _HTML_TAGS) | {"llm"})
        for node in list(self.document.findall(addnodes.only)):
            in_html = tags.eval_condition(node["expr"])
            in_markdown = markdown_tags.eval_condition(node["expr"])
            if in_html == in_markdown:
                continue
            if in_html:
                node.replace_self(html_only("", *node.children))
            else:
                node.replace_self(markdown_only("", "", *node.children))


def _pass(self: HTML5Translator, node: nodes.Element) -> None:
    pass


def _skip(self: HTML5Translator, node: nodes.Element) -> None:
    raise nodes.SkipNode


def setup_only(app: Sphinx) -> None:
    app.add_node(html_only, html=(_pass, _pass))
    app.add_node(markdown_only, html=(_skip, None))
    app.add_post_transform(_SplitOnlyNodes)
