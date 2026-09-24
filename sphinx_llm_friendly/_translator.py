from __future__ import annotations

import dataclasses
import posixpath
import re
from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import urlsplit, urlunsplit

from docutils import nodes
from sphinx import addnodes
from sphinx.util.docutils import SphinxTranslator

from ._contexts import (
    DOC_INFO_CONTEXT,
    ITALIC_CONTEXT,
    STRONG_CONTEXT,
    SUBSCRIPT_CONTEXT,
    CommaSeparatedContext,
    ContextStatus,
    FootNoteContext,
    IndentContext,
    ListMarker,
    PushBox,
    PushContext,
    SubContext,
    SubContextParams,
    TableContext,
    TitleContext,
    UniqueString,
    WrappedContext,
)
from ._escape import escape_markdown_chars
from ._exclude import is_excluded
from ._intersphinx import to_markdown_url

if TYPE_CHECKING:
    from sphinx.builders.html import StandaloneHTMLBuilder

VISIT_DEPART_PATTERN = re.compile("(visit|depart)_(.+)")
SKIP = UniqueString("skip")

DOC_INFO_FIELDS = (
    "author",
    "contact",
    "copyright",
    "date",
    "organization",
    "revision",
    "status",
    "version",
)

# Defines context items, skip, or None (keep processing sub-tree).
PREDEFINED_ELEMENTS: dict[str, PushContext[Any] | PushBox | UniqueString | None] = dict(
    # Doctree elements for which Markdown element is <prefix><content><suffix>
    emphasis=ITALIC_CONTEXT,
    strong=STRONG_CONTEXT,
    subscript=SUBSCRIPT_CONTEXT,
    superscript=SUBSCRIPT_CONTEXT,
    desc_annotation=ITALIC_CONTEXT,
    literal_strong=STRONG_CONTEXT,
    literal_emphasis=ITALIC_CONTEXT,
    field_name=PushContext(WrappedContext, "**", ":**"),  # e.g 'returns', 'parameters'
    # Doc info elements
    docinfo=DOC_INFO_CONTEXT,
    docinfo_item=DOC_INFO_CONTEXT,
    **dict.fromkeys(DOC_INFO_FIELDS, DOC_INFO_CONTEXT),
    authors=None,  # not used: visit_author is called anyway for each author.
    # Admonitions
    important=PushBox("IMPORTANT"),
    warning=PushBox("WARNING"),
    note=PushBox("NOTE"),
    seealso=PushBox("NOTE", "See also"),
    attention=PushBox("IMPORTANT"),
    hint=PushBox("TIP"),
    tip=PushBox("TIP"),
    caution=PushBox("CAUTION"),
    danger=PushBox("CAUTION"),
    error=PushBox("CAUTION"),
    admonition=PushBox("NOTE"),
    sidebar=PushBox("TIP"),
    versionmodified=PushBox(
        "WARNING"
    ),  # “versionadded”, “versionchanged” and “deprecated” directives.
    # Doctree elements to skip subtree
    autosummary_toc=SKIP,
    nbplot_epilogue=SKIP,
    nbplot_not_rendered=SKIP,
    nbplot_container=SKIP,
    code_links=SKIP,
    index=SKIP,
    meta=SKIP,
    substitution_definition=SKIP,  # the doctree already contains the text with substitutions applied.
    runrole_reference=SKIP,
    toctree=SKIP,
    viewcode_anchor=SKIP,
    # Doctree elements to ignore
    document=None,
    container=None,
    inline=None,
    PassthroughTextElement=None,  # sphinx-design
    abbreviation=None,
    definition_list=None,
    definition_list_item=None,
    glossary=None,
    field_list_item=None,
    mpl_hint=None,
    pending_xref=None,
    compound=None,
    desc_addname=None,  # module pre-roll for class/method
    desc_content=None,  # the description of the class/method
    desc_name=None,  # name of the class/method
    title_reference=None,
    autosummary_table=None,  # Sphinx autosummary
    # See https://www.sphinx-doc.org/en/master/usage/extensions/autosummary.html.
    # Ignored table elements
    raw=None,
    tabular_col_spec=None,
    colspec=None,
    tgroup=None,
    figure=None,
    caption=None,
    desc_signature_line=None,
    target=None,
)


_F = TypeVar("_F", bound=Callable[..., None])


def _assign_visit_method(method: _F, variable: str) -> _F:
    match = VISIT_DEPART_PATTERN.fullmatch(method.__name__)
    assert match is not None
    state, _ = match.groups()
    assert state == "visit"
    setattr(method, variable, True)
    return method


def pushing_context(method: _F) -> _F:
    """Marks method as pushing context"""
    return _assign_visit_method(method, "__pushing_context__")


def pushing_status(method: _F) -> _F:
    """Marks method as status context"""
    return _assign_visit_method(method, "__pushing_status__")


def _in_signature(node: nodes.Node) -> bool:
    parent = node.parent
    while parent is not None:
        if isinstance(parent, addnodes.desc_signature):
            return True
        parent = parent.parent
    return False


class MarkdownTranslator(SphinxTranslator):
    def __init__(
        self,
        document: nodes.document,
        builder: StandaloneHTMLBuilder,
        single_file: bool = False,
    ):
        super().__init__(document, builder)
        self.builder: StandaloneHTMLBuilder = builder
        # In llms-full.txt, the documentation title is the only H1, internal
        # links become plain text, and local files are relative to the root.
        self._single_file = single_file
        # Warn only once per writer about unsupported elements
        self._warned: set[str] = set()

        # FIFO Sub context allow us to handle unique cases when post-processing is required
        self._ctx_queue: list[SubContext] = [SubContext()]
        self._doc_info: SubContext = SubContext()
        self._status_queue: list[ContextStatus] = [ContextStatus()]

    @property
    def ctx(self) -> SubContext:
        return self._ctx_queue[-1]

    def _push_context(self, ctx: SubContext) -> None:
        self._ctx_queue.append(ctx)

    def _title_level(self, base_level: int) -> int:
        return min(6, max(1, base_level + int(self._single_file)))

    def _pop_context(self, _node: nodes.Node | None = None, count: int = 1) -> None:
        for _ in range(count):
            if len(self._ctx_queue) <= 1:
                break

            last_ctx = self._ctx_queue.pop()
            ctx = self.ctx if last_ctx.params.target == "body" else self._doc_info
            ctx.add(
                last_ctx.make(), last_ctx.params.prefix_eol, last_ctx.params.suffix_eol
            )

    def _push_box(self, title: str, heading: str | None = None) -> None:
        self.add(f"> [!{title}]")
        self._push_context(
            IndentContext(prefix="> ", empty=True, params=SubContextParams(1, 2))
        )
        self._push_status(section_level=3)
        if heading is not None:
            self.add(f"### {heading}")

    @property
    def status(self) -> ContextStatus:
        return self._status_queue[-1]

    def _push_status(self, **changes: Any) -> None:
        cur_status = self.status
        self._status_queue.append(dataclasses.replace(cur_status, **changes))

    def _pop_status(self, _node: nodes.Node | None = None, count: int = 1) -> None:
        count = min(len(self._status_queue) - 1, count)
        self._status_queue = self._status_queue[:-count]

    def _pop_context_and_status(self, node: nodes.Node | None = None) -> None:
        self._pop_context(node)
        self._pop_status(node)

    def astext(self) -> str:
        """Return the final formatted document as a string."""
        self._pop_context(count=2**31)
        assert len(self._ctx_queue) == 1

        ctx = SubContext()
        for sub_ctx in (self._doc_info, self._ctx_queue[0]):
            ctx.add(sub_ctx.make().strip(), prefix_eol=2, suffix_eol=1)
        ctx.force_eol(1)
        return ctx.make()

    def add(self, value: str, prefix_eol: int = 0, suffix_eol: int = 0) -> None:
        """See `SubContext.add()`"""
        self.ctx.add(value, prefix_eol, suffix_eol)

    def ensure_eol(self, count: int = 1) -> None:
        """Ensure the last line in current base is terminated by X new lines."""
        self.ctx.ensure_eol(count)

    def _pass(self, _node: nodes.Node | None = None) -> None:
        pass

    def _skip(self, _node: nodes.Node | None = None) -> None:
        raise nodes.SkipNode

    def _has_attr(self, item: str) -> bool:
        try:
            super().__getattribute__(item)
            return True
        except AttributeError:
            return False

    def _get_attr(self, item: str, default: Any = None) -> Any:
        try:
            return super().__getattribute__(item)
        except AttributeError:
            return default

    def __getattribute__(self, item: str) -> Any:
        """Uses some predefined rules to reduce the visit/depart method clutter in the class"""
        try:
            # First try to get an existing attribute
            return super().__getattribute__(item)
        except AttributeError as ex:
            predefined_method = self._find_predefined_method(item)
            if predefined_method is not None:
                return predefined_method
            raise ex

    def _find_predefined_action(
        self, state: str, element: str
    ) -> Callable[[nodes.Node], None] | None:
        action = PREDEFINED_ELEMENTS.get(element, "__undefined__")
        if action is None:
            return self._pass
        if action is SKIP:
            return self._skip
        if isinstance(action, PushContext):
            if state == "visit":
                return lambda node: self._push_context(action.create(node, element))
            return self._pop_context
        if isinstance(action, PushBox):
            if state == "visit":
                return lambda _node: self._push_box(action.title, action.heading)
            return self._pop_context_and_status
        return None

    def _find_pushing_method(
        self, state: str, element: str
    ) -> Callable[[nodes.Node], None] | None:
        if state != "depart":
            return None

        # If the visit method is marked as pushing, then pop the context/status
        visit_method = self._get_attr(f"visit_{element}", None)
        is_pushing_ctx = getattr(visit_method, "__pushing_context__", False)
        is_pushing_status = getattr(visit_method, "__pushing_status__", False)
        if is_pushing_ctx and is_pushing_status:
            return self._pop_context_and_status
        if is_pushing_ctx:
            return self._pop_context
        if is_pushing_status:
            return self._pop_status
        return None

    def _is_element_defined(self, element: str) -> bool:
        return self._has_attr(f"visit_{element}") or self._has_attr(f"depart_{element}")

    def _find_predefined_method(self, item: str) -> Callable[[nodes.Node], None] | None:
        match = VISIT_DEPART_PATTERN.fullmatch(item)
        if match is None:
            # We only care about visit/depart methods
            return None
        state, element = match.groups()

        method = self._find_predefined_action(state, element)
        if method is not None:
            return method

        method = self._find_pushing_method(state, element)
        if method is not None:
            return method

        # If one of the handlers is defined, automatically add the other as an empty handler
        if self._is_element_defined(element):
            return self._pass

        return None

    def unknown_visit(self, node: nodes.Node) -> None:
        """Warn once per instance for unsupported nodes."""
        node_type = node.__class__.__name__
        if node_type not in self._warned:
            super().unknown_visit(node)
            self._warned.add(node_type)
        raise nodes.SkipNode

    ################################################################################
    # visit/depart handlers
    ################################################################################

    def visit_image(self, node: nodes.Element) -> None:
        """Image directive."""
        uri = node["uri"]
        if self._single_file and uri.startswith(f"{self.builder.imgpath}/"):
            uri = posixpath.join("_images", posixpath.basename(uri))
        alt = node.attributes.get("alt", "image")
        # We don't need to add EOL before/after the image.
        # It will be handled by the visit/depart handlers of the paragraph.
        self.add(f"![{alt}]({uri})")

    # noinspection PyPep8Naming
    def visit_Text(self, node: nodes.Text) -> None:
        text = node.astext().replace("\r", "")
        if self.status.escape_text:
            text = escape_markdown_chars(text)
        self.add(text)

    @pushing_context
    @pushing_status
    def visit_comment(self, _node: nodes.Element) -> None:
        self._push_status(escape_text=False)
        self._push_context(WrappedContext("<!-- ", " -->", params=SubContextParams(1)))

    @pushing_context
    def visit_paragraph(self, _node: nodes.Element) -> None:
        if self.status.list_marker is None:
            params = SubContextParams(2, 2)
        else:
            # Full paragraph spacing inside a list might trigger redundant spacing for some markdown compilers.
            # So we will add double EOL after the paragraph only if the next element requires it (e.g., code block).
            params = SubContextParams(2, 1)
        self._push_context(SubContext(params))

    visit_compact_paragraph = visit_paragraph

    ################################################################################
    # Line block
    ################################################################################
    # line_block
    #   line
    #   line
    #   line
    ################################################################################

    @pushing_context
    def visit_line_block(self, _node: nodes.Element) -> None:
        self._push_context(SubContext(SubContextParams(1, 1)))

    @pushing_context
    def visit_line(self, _node: nodes.Element) -> None:
        self._push_context(SubContext(SubContextParams(1, 1)))

    ################################################################################
    # Definition / Glossaries
    # A definition_list can be outside a glossary. In which case, the term won't
    # have IDs, thus not having anchors.
    ################################################################################
    # glossary
    #   definition_list
    #     definition_list_item
    #       term
    #         index entries
    #       definition
    #         paragraph
    ################################################################################

    def visit_term(self, _node: nodes.Element) -> None:
        self.ensure_eol(2)

    @pushing_context
    def visit_definition(self, _node: nodes.Element) -> None:
        self._push_context(
            IndentContext(
                ": ",
                only_first=True,
                support_multi_line_break=True,
                params=SubContextParams(1, 2),
            )
        )

    def visit_math_block(self, _node: nodes.Element) -> None:
        """docutils math block"""
        self._push_status(escape_text=False, preserve_line_breaks=True)
        self.add("$$", prefix_eol=1, suffix_eol=1)

    def depart_math_block(self, _node: nodes.Element) -> None:
        """docutils math block"""
        self.add("$$", prefix_eol=1, suffix_eol=2)
        self._pop_status()

    def visit_math(self, _node: nodes.Element) -> None:
        """docutils math node"""
        self._push_status(escape_text=False)
        self.add("$")

    def depart_math(self, _node: nodes.Element) -> None:
        """docutils math node"""
        self.add("$")
        self._pop_status()

    def visit_literal(self, _node: nodes.Element) -> None:
        self._push_status(escape_text=False)
        self.add("`")

    def depart_literal(self, _node: nodes.Element) -> None:
        self.add("`")
        self._pop_status()

    def visit_literal_block(self, node: nodes.Element) -> None:
        self._push_status(escape_text=False, preserve_line_breaks=True)
        code_type = ""
        classes: list[str] = node.get("classes", [])
        if "code" in classes:
            code_idx = classes.index("code") + 1
            if code_idx < len(classes):
                code_type = classes[code_idx]
        if "language" in node:
            code_type = node["language"]
        elif self.status.code_language:
            code_type = self.status.code_language
        if code_type == "default":
            code_type = ""
        self.add(f"```{code_type}", prefix_eol=1, suffix_eol=1)

    def depart_literal_block(self, _node: nodes.Element) -> None:
        self.add("```", prefix_eol=1, suffix_eol=2)
        self._pop_status()

    def visit_doctest_block(self, _node: nodes.Element) -> None:
        self._push_status(escape_text=False, preserve_line_breaks=True)
        self.add("```pycon", prefix_eol=1, suffix_eol=1)

    depart_doctest_block = depart_literal_block  # type: ignore[assignment]

    @pushing_context
    def visit_block_quote(self, _node: nodes.Element) -> None:
        self._push_context(IndentContext("> "))

    def visit_problematic(self, node: nodes.Element) -> None:
        self.add(f"```\n{node.astext()}\n```", prefix_eol=2, suffix_eol=2)
        raise nodes.SkipNode

    @pushing_status
    def visit_section(self, _node: nodes.Element) -> None:
        self.ensure_eol(2)
        self._push_status(section_level=self.status.section_level + 1)

    @pushing_context
    def visit_title(self, _node: nodes.Element) -> None:
        level = 4 if isinstance(self.ctx, TableContext) else self.status.section_level
        self._push_context(TitleContext(self._title_level(level), breaker=" "))

    @pushing_context
    @pushing_status
    def visit_subtitle(self, _node: nodes.Element) -> None:  # pragma: no cover
        """
        Docutils does not promote subtitles, so this might never be called.
        However, we keep it here in case some future version will change this behaviour.
        """
        self._push_status(section_level=self.status.section_level + 1)
        self._push_context(
            TitleContext(self._title_level(self.status.section_level), breaker=" ")
        )

    @pushing_context
    def visit_rubric(self, _node: nodes.Element) -> None:
        """Sphinx Rubric, a heading without relation to the document sectioning"""
        self._push_context(TitleContext(self._title_level(3), breaker=" "))

    def visit_transition(self, _node: nodes.Element) -> None:
        """Simply replace a transition by a horizontal rule."""
        # Can use three or more '*', '_' or '-'.
        self.add("---", prefix_eol=2, suffix_eol=1)
        raise nodes.SkipNode

    def visit_only(self, node: nodes.Element) -> None:
        expr = node.get("expr", "")
        tags = getattr(self.builder, "tags", None)
        if not expr or tags is None:
            return
        if not tags.eval_condition(expr):
            raise nodes.SkipNode

    def _fetch_ref_uri(self, node: nodes.Element) -> str:
        uri = node.get("refuri", "")

        if not node.get("internal", self.status.default_ref_internal):
            return to_markdown_url(uri)

        # The Markdown output has no anchors, so same-page references have no
        # URL and references to other pages link to the whole page.
        if node.get("refid") is not None:
            return ""
        return self._markdown_page_uri(uri)

    def _markdown_page_uri(self, uri: str) -> str:
        parts = urlsplit(uri)
        if not parts.path:
            return ""
        if not parts.path.endswith(".html"):
            return uri
        docname = self._target_docname(parts.path)
        env = self.builder.env
        if docname not in env.found_docs or is_excluded(env, docname):
            return uri
        if docname == self.builder.current_docname:
            return ""
        return urlunsplit(parts._replace(path=f"{parts.path[:-5]}.md", fragment=""))

    def _target_docname(self, path: str) -> str:
        if not path:
            return self.builder.current_docname
        page_uri = self.builder.get_target_uri(self.builder.current_docname)
        return posixpath.normpath(
            posixpath.join(posixpath.dirname(page_uri), path.removesuffix(".html"))
        )

    @cached_property
    def _label_titles(self) -> dict[tuple[str, str], str]:
        labels = self.builder.env.get_domain("std").labels  # type: ignore[attr-defined]
        return {
            (docname, label_id): title
            for docname, label_id, title in labels.values()
            if title
        }

    def _ref_heading(self, node: nodes.Element) -> str:
        """Return the heading targeted by the ``:ref:`` reference *node*, if it
        is neither its text nor the title of its page, which a reader cannot
        find from the reference alone.
        """
        if not any(
            "std-ref" in child.get("classes", [])
            for child in node.children
            if isinstance(child, nodes.Element)
        ):
            return ""
        if refid := node.get("refid"):
            docname, label_id = self.builder.current_docname, refid
        else:
            parts = urlsplit(node.get("refuri", ""))
            docname, label_id = self._target_docname(parts.path), parts.fragment
        heading = self._label_titles.get((docname, label_id), "")
        page_title = self.builder.env.titles.get(docname)
        known = {node.astext(), page_title.astext() if page_title else ""}
        if heading.casefold() in {text.casefold() for text in known}:
            return ""
        return heading

    @pushing_context
    def visit_reference(self, node: nodes.Element) -> None:
        # If this reference was already moved into a card title, skip it.
        if node.get("md_moved_to_title", False):
            raise nodes.SkipNode

        is_internal = bool(node.get("internal", self.status.default_ref_internal))
        if is_internal:
            url = "" if self._single_file else self._fetch_ref_uri(node)
        elif _in_signature(node):
            url = ""
        else:
            url = self._fetch_ref_uri(node)
        heading = self._ref_heading(node) if is_internal else ""
        if url:
            title = heading.replace("\\", "\\\\").replace('"', '\\"')
            title = f' "{title}"' if title else ""
            self._push_context(WrappedContext("[", f"]({url}{title})"))
        else:
            if heading and self.status.escape_text:
                heading = escape_markdown_chars(heading)
            suffix = f" (see {heading})" if heading else ""
            self._push_context(WrappedContext("", suffix))

    def visit_pending_xref(self, node: nodes.Element) -> None:
        # Keep default behavior (child text passes through), unless this node
        # was already moved into a card title link.
        if node.get("md_moved_to_title", False):
            raise nodes.SkipNode

    @pushing_context
    def visit_download_reference(self, node: nodes.Element) -> None:
        # Sphinx sets `refuri` for external targets; preserve those URLs verbatim.
        if "refuri" in node:
            target = node["refuri"]
        # For readable internal targets, `filename` is the registered, hashed
        # destination. Link to the copied file relative to the current output page.
        elif "filename" in node:
            downloads = "_downloads" if self._single_file else self.builder.dlpath
            target = posixpath.join(downloads, node["filename"])
        # If Sphinx could not register the internal file, only its original
        # `reftarget` remains.
        else:
            target = node.get("reftarget", "")
        self._push_context(WrappedContext("[", f"]({target})"))

    def visit_compound(self, node: nodes.Element) -> None:
        if self._single_file and "toctree-wrapper" in node["classes"]:
            raise nodes.SkipNode

    @pushing_context
    @pushing_status
    def visit_topic(self, _node: nodes.Element) -> None:
        self._push_status(default_ref_internal=True, section_level=5)
        self._push_context(IndentContext("> ", empty=True))

    def visit_container(self, node: nodes.Element) -> None:
        """Handle generic container nodes and special-case sphinx-design cards.

        We push a blockquote context for top-level sphinx-design cards (class
        `sd-card`) so their contents are rendered as a Markdown blockquote. We
        also special-case containers with class `sd-card-title` to render the
        title as a linked level-4 heading inside the blockquote.
        """
        classes = node.attributes.get("classes", []) or []

        # Handle sphinx-design card containers and titles using small helpers
        # to keep this method simple and under the complexity threshold.
        if "sd-card" in classes:
            self._handle_sd_card(node)
            return

        if "sd-card-title" in classes:
            self._handle_sd_card_title(node)
            return

    def _handle_sd_card(self, node: nodes.Element) -> None:
        # Ensure an extra blank line after the card so adjacent cards don't
        # merge into the same blockquote in Markdown output.
        self._push_context(
            IndentContext("> ", empty=True, params=SubContextParams(1, 2))
        )
        # mark the node so depart_container knows to pop
        # Store a marker in the node attributes when possible so downstream
        # handlers can detect that we pushed a card context. Use the node
        # attribute mapping if available to avoid touching protected members.
        if hasattr(node, "attributes") and isinstance(node.attributes, dict):
            node["md_card_pushed"] = True

    def _find_card_container(self, node: nodes.Element) -> nodes.Element | None:
        container: nodes.Element | None = node
        while container is not None and "sd-card" not in (
            container.attributes.get("classes", []) or []
        ):
            container = getattr(container, "parent", None)
        return container

    def _find_stretched_link(
        self, container: nodes.Element | None
    ) -> nodes.Element | None:
        if container is None:
            return None
        for child in container.findall(nodes.Element):
            if "sd-stretched-link" in child.get("classes", []):
                return child
        return None

    def _href_from_link_node(self, link_node: nodes.Element | None) -> str | None:
        if link_node is None:
            return None
        if isinstance(link_node, nodes.reference):
            try:
                return self._fetch_ref_uri(link_node)
            except (AttributeError, KeyError, TypeError):
                return ""
        return link_node.get("refuri") or link_node.get("reftarget") or ""

    def _normalize_card_href(self, href: str | None) -> str | None:
        if not href:
            return href
        if href.endswith(".html"):
            return href[:-5] + ".md"
        is_http = href.startswith(("http://", "https://"))
        if not (is_http or href.endswith(".md")):
            return href + ".md"
        return href

    def _handle_sd_card_title(self, node: nodes.Element) -> None:
        container = self._find_card_container(node)
        link_node = self._find_stretched_link(container)

        title = node.astext().strip()
        level = self._title_level(4)

        href = self._href_from_link_node(link_node)
        if link_node is not None:
            link_node["md_moved_to_title"] = True

        href = self._normalize_card_href(href)

        if self.status.escape_text:
            title = escape_markdown_chars(title)

        is_internal_href = href and not href.startswith(("http://", "https://"))

        if self._single_file and is_internal_href:
            self.add(f"{('#' * level)} {title}", prefix_eol=1, suffix_eol=1)
        elif href:
            self.add(f"{('#' * level)} [{title}]({href})", prefix_eol=1, suffix_eol=1)
        else:
            self.add(f"{('#' * level)} {title}", prefix_eol=1, suffix_eol=1)

        raise nodes.SkipNode

    def depart_container(self, node: nodes.Element) -> None:
        # If we marked the node as having pushed a card context, pop it now.
        if node.get("md_card_pushed", False) and len(self._ctx_queue) > 1:
            self._pop_context(node)

    ################################################################################
    # lists
    ################################################################################
    # enumerated_list/bullet_list
    #     list_item
    #       paragraph (optional)
    ###############################################################################

    def _start_list(self, marker: int | str) -> None:
        self.ensure_eol()
        if isinstance(marker, str) and marker[-1] != " ":
            marker += " "
        self._push_status(list_marker=ListMarker(marker))

    def _end_list(self, _node: nodes.Node | None = None) -> None:
        self._pop_status()
        # We need two line breaks to make sure the next paragraph will not merge into the list
        self.ensure_eol(2)

    def _start_list_item(self, _node: nodes.Node | None = None) -> None:
        marker = self.status.list_marker
        assert marker is not None
        marker.inc()
        self._push_context(
            IndentContext(marker, only_first=True, params=SubContextParams(1, 1))
        )

    _end_list_item = _pop_context

    def visit_enumerated_list(self, _node: nodes.Element) -> None:
        self._start_list(0)

    depart_enumerated_list = _end_list  # type: ignore[assignment]

    def visit_bullet_list(self, node: nodes.Element) -> None:
        self._start_list(node.attributes.get("bullet", "*"))

    depart_bullet_list = _end_list  # type: ignore[assignment]
    visit_list_item = _start_list_item  # type: ignore[assignment]
    depart_list_item = _end_list_item  # type: ignore[assignment]

    ################################################################################
    # option lists
    ################################################################################
    # option_list
    #   option_list_item
    #     option_group
    #     description
    ###############################################################################

    def visit_option_list(self, _node: nodes.Element) -> None:
        self._start_list("*")

    depart_option_list = _end_list  # type: ignore[assignment]
    visit_option_list_item = _start_list_item  # type: ignore[assignment]
    depart_option_list_item = _end_list_item  # type: ignore[assignment]

    def visit_option_group(self, node: nodes.Element) -> None:
        self.add(f"`{escape_markdown_chars(node.astext())}`", suffix_eol=1)
        raise nodes.SkipNode

    def visit_description(self, _node: nodes.Element) -> None:
        pass

    depart_description = _pass  # type: ignore[assignment]

    ################################################################################
    # desc
    ################################################################################
    # desc (desctype: {function, class, method, etc.)
    #   desc_signature
    #     desc_signature_line (optional nesting)
    #         desc_name
    #           desc_annotation (optional)
    #         desc_parameterlist
    #           desc_annotation
    #           desc_parameter
    #         desc_returns
    #   desc_content
    #     field_list
    #       field
    #         field_name (e.g 'returns/parameters/raises')
    #         field_body
    ################################################################################

    @pushing_status
    def visit_desc(self, node: nodes.Element) -> None:
        self._push_status(desc_type=node.attributes.get("desctype", ""))

    @pushing_context
    def visit_desc_signature(self, node: nodes.Element) -> None:
        """the main signature of class/method"""
        # We don't want methods to be at the same level as classes,
        # If signature has a non-null class, that's means it is a signature
        # of a class method
        h_level = 4 if node.get("class", None) else 3
        self._push_context(TitleContext(self._title_level(h_level)))

    def visit_desc_parameterlist(self, _node: nodes.Element) -> None:
        self._push_context(WrappedContext("(", ")", wrap_empty=True))
        self._push_context(CommaSeparatedContext(", "))

    def depart_desc_parameterlist(self, _node: nodes.Element) -> None:
        self._pop_context(count=2)

    @property
    def sep_ctx(self) -> CommaSeparatedContext | None:
        for ctx in reversed(self._ctx_queue):
            if isinstance(ctx, CommaSeparatedContext):
                return ctx
        return None

    def visit_desc_parameter(self, _node: nodes.Element) -> None:
        """single method/class ctr param"""
        sep_ctx = self.sep_ctx
        if sep_ctx is not None:
            sep_ctx.enter_parameter()

    def depart_desc_parameter(self, _node: nodes.Element) -> None:
        sep_ctx = self.sep_ctx
        if sep_ctx is not None:
            sep_ctx.exit_parameter()

    @pushing_context
    def visit_desc_optional(self, _node: nodes.Element) -> None:
        self._push_context(WrappedContext("[", "]"))

    def visit_field_list(self, _node: nodes.Element) -> None:
        self._start_list("*")

    depart_field_list = _end_list  # type: ignore[assignment]
    visit_field = _start_list_item  # type: ignore[assignment]
    depart_field = _end_list_item  # type: ignore[assignment]

    def visit_desc_returns(self, _node: nodes.Element) -> None:
        self.add(" → ")

    @pushing_context
    def visit_field_body(self, _node: nodes.Element) -> None:
        self._push_context(SubContext(SubContextParams(1, 1)))

    def visit_highlightlang(self, node: nodes.Element) -> None:
        """Apply default language for subsequent literal blocks."""
        lang = node.get("lang", "")
        self._status_queue[-1] = dataclasses.replace(self.status, code_language=lang)

    ################################################################################
    # tables
    ################################################################################
    # table
    #   tgroup [cols=x]
    #     colspec
    #     thead
    #       row
    #         entry
    #           paragraph (optional)
    #     tbody
    #       row
    #         entry
    #           paragraph (optional)
    ###############################################################################

    @property
    def table_ctx(self) -> TableContext:
        ctx = self.ctx
        assert isinstance(ctx, TableContext)
        return ctx

    @pushing_context
    def visit_table(self, _node: nodes.Element) -> None:
        self._push_context(
            TableContext(params=SubContextParams(2, 1), cell_breaker=" ")
        )

    def visit_thead(self, _node: nodes.Element) -> None:
        self.table_ctx.enter_head()

    def depart_thead(self, _node: nodes.Element) -> None:
        self.table_ctx.exit_head()

    def visit_tbody(self, _node: nodes.Element) -> None:
        self.table_ctx.enter_body()

    def depart_tbody(self, _node: nodes.Element) -> None:
        self.table_ctx.exit_body()

    def visit_row(self, _node: nodes.Element) -> None:
        self.table_ctx.enter_row()

    def depart_row(self, _node: nodes.Element) -> None:
        self.table_ctx.exit_row()

    def visit_entry(self, _node: nodes.Element) -> None:
        self.table_ctx.enter_entry()

    def depart_entry(self, _node: nodes.Element) -> None:
        self.table_ctx.exit_entry()

    ################################################################################
    # footnote
    ################################################################################
    # footnote_reference
    # ...
    # footnote
    #   label
    #   paragraph
    ###############################################################################

    @property
    def footnote_ctx(self) -> FootNoteContext:
        ctx = self.ctx
        assert isinstance(ctx, FootNoteContext)
        return ctx

    @pushing_context
    def visit_footnote_reference(self, _node: nodes.Element) -> None:
        # https://www.markdownguide.org/extended-syntax/#footnotes
        self._push_context(WrappedContext("[^", "]"))

    @pushing_context
    def visit_footnote(self, node: nodes.Element) -> None:
        ids = node.get("ids", "")
        if isinstance(ids, list | tuple):
            ids = ",".join(ids)
        names = node.get("names", "")
        if isinstance(names, list | tuple):
            names = ",".join(names)
        # https://www.markdownguide.org/extended-syntax/#footnotes
        self._push_context(FootNoteContext(ids, names, params=SubContextParams(1, 1)))

    def visit_label(self, node: nodes.Element) -> None:
        try:
            self.footnote_ctx.visit_label()
        except AssertionError:
            self.unknown_visit(node)

    def depart_label(self, node: nodes.Element) -> None:
        try:
            self.footnote_ctx.depart_label()
        except AssertionError:
            self.unknown_visit(node)
