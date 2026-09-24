from __future__ import annotations

from docutils import nodes

_NAV_ARTIFACT_TEXTS = frozenset({"genindex", "modindex", "search"})


def _remove_node(node: nodes.Node) -> None:
    if node.parent is not None:
        node.parent.remove(node)


def _is_nav_artifact_list_item(node: nodes.Node) -> bool:
    text = " ".join(node.astext().split()).strip().lower()
    return text in _NAV_ARTIFACT_TEXTS


def _remove_nav_artifact_lists(doc: nodes.document) -> None:
    for bullet_list in list(doc.findall(nodes.bullet_list)):
        list_items = [
            child
            for child in bullet_list.children
            if isinstance(child, nodes.list_item)
        ]
        if list_items and all(_is_nav_artifact_list_item(item) for item in list_items):
            _remove_node(bullet_list)


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
    """Return a copy of *doc* without the nodes that are noise in LLM-oriented
    output: targets, transitions, comments, index links, and the sections and
    lists that end up empty as a result.
    """
    llm_doc = doc.deepcopy()
    for node_type in (nodes.target, nodes.transition, nodes.comment):
        for node in list(llm_doc.findall(node_type)):
            _remove_node(node)
    _remove_nav_artifact_lists(llm_doc)
    _prune_empty_containers(llm_doc)
    return llm_doc
