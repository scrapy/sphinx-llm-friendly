from __future__ import annotations

import posixpath

from docutils import nodes

from ._only import html_only, markdown_only

_NAV_ARTIFACT_PAGES = frozenset({"genindex.html", "py-modindex.html", "search.html"})


def _remove_node(node: nodes.Node) -> None:
    if node.parent is not None:
        node.parent.remove(node)


def _is_nav_artifact_list_item(node: nodes.Element) -> bool:
    return any(
        posixpath.basename(reference.get("refuri", "")) in _NAV_ARTIFACT_PAGES
        for reference in node.findall(nodes.reference)
    )


def _remove_nav_artifact_lists(doc: nodes.document) -> None:
    for bullet_list in list(doc.findall(nodes.bullet_list)):
        list_items = [
            child
            for child in bullet_list.children
            if isinstance(child, nodes.list_item)
        ]
        if list_items and all(_is_nav_artifact_list_item(item) for item in list_items):
            _remove_node(bullet_list)


def _undo_html_changes(doc: nodes.document) -> None:
    # The HTML writer gives specific admonitions (note, warning, …) a title,
    # html_scaled_image_link wraps scaled images in a link to themselves, and
    # sphinx.ext.viewcode adds [source] links to the highlighted source code.
    for admonition in list(doc.findall(nodes.Element)):
        title = admonition.children[0] if admonition.children else None
        if (
            isinstance(admonition, nodes.Admonition)
            and isinstance(title, nodes.title)
            and title.rawsource == type(admonition).__name__
        ):
            admonition.remove(title)
    for image in list(doc.findall(nodes.image)):
        reference = image.parent
        if (
            isinstance(reference, nodes.reference)
            and reference.get("refuri") == image["uri"]
            and len(reference.children) == 1
        ):
            reference.replace_self(image)
    for inline in list(doc.findall(nodes.inline)):
        if "viewcode-link" in inline["classes"]:
            _remove_node(inline.parent)


def _undo_sphinx_design_changes(doc: nodes.document) -> None:
    # sphinx-design turns dropdowns and tab sets into HTML-specific nodes,
    # which we turn back into rubrics followed by their content.
    for dropdown in list(doc.findall(nodes.Element)):
        if type(dropdown).__name__ != "dropdown_main":
            continue
        title, body = dropdown.children
        title_text = next(
            node
            for node in title.findall(nodes.inline)
            if "sd-summary-text" in node["classes"]
        )
        children: list[nodes.Node] = list(body.children)
        if not all(isinstance(child, nodes.raw) for child in title_text.children):
            children.insert(0, nodes.rubric("", "", *title_text.children))
        dropdown.parent.replace(dropdown, children)
    for tab_set in list(doc.findall(nodes.container)):
        if tab_set.get("design_component") != "tab-set":
            continue
        # Each tab is an sd_tab_input, sd_tab_label, content triple.
        tabs = tab_set.children
        children = []
        for label, content in zip(tabs[1::3], tabs[2::3], strict=False):
            children += [nodes.rubric("", "", *label.children), *content.children]
        tab_set.parent.replace(tab_set, children)


def _prune_empty_containers(doc: nodes.document) -> None:
    changed = True
    while changed:
        changed = False

        for bullet_list in list(doc.findall(nodes.bullet_list)):
            if len(bullet_list.children) == 0:
                _remove_node(bullet_list)
                changed = True

        for section in list(doc.findall(nodes.section)):
            if all(isinstance(child, nodes.title) for child in section.children):
                _remove_node(section)
                changed = True


def prepare_doctree_for_llm(doc: nodes.document) -> nodes.document:
    """Return a copy of *doc*, as written by the HTML builder, without the
    nodes that are noise in LLM-oriented output: targets, transitions,
    comments, index links, elements with the ``llm-friendly-exclude`` class,
    and the sections and lists that end up empty as a result.
    """
    llm_doc = doc.deepcopy()
    _undo_html_changes(llm_doc)
    _undo_sphinx_design_changes(llm_doc)
    for html_node in list(llm_doc.findall(html_only)):
        _remove_node(html_node)
    for markdown_node in list(llm_doc.findall(markdown_only)):
        markdown_node.parent.replace(markdown_node, markdown_node.children)
    for node_type in (nodes.target, nodes.transition, nodes.comment):
        for node in list(llm_doc.findall(node_type)):
            _remove_node(node)
    for element in list(llm_doc.findall(nodes.Element)):
        if "llm-friendly-exclude" in element["classes"]:
            _remove_node(element)
    _remove_nav_artifact_lists(llm_doc)
    _prune_empty_containers(llm_doc)
    return llm_doc
