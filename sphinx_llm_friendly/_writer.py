from __future__ import annotations

from typing import TYPE_CHECKING, cast

from docutils import writers

if TYPE_CHECKING:
    from docutils import nodes
    from sphinx.builders import Builder

    from ._translator import MarkdownTranslator


class MarkdownWriter(writers.Writer):  # type: ignore[type-arg]
    supported = ("markdown",)

    def __init__(self, builder: Builder):
        super().__init__()
        self.builder = builder

    def translate(self) -> None:
        document = cast("nodes.document", self.document)
        visitor = cast(
            "MarkdownTranslator", self.builder.create_translator(document, self.builder)
        )
        document.walkabout(visitor)
        self.output = visitor.astext()
