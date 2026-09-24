from __future__ import annotations

from functools import cache
from pathlib import PurePath
from typing import TYPE_CHECKING

from sphinx.util.matching import compile_matchers

if TYPE_CHECKING:
    from collections.abc import Callable

    from sphinx.application import Sphinx


@cache
def _matchers(patterns: tuple[str, ...]) -> list[Callable[[str], bool]]:
    return compile_matchers(patterns)  # type: ignore[return-value]


def is_excluded(app: Sphinx, docname: str) -> bool:
    """Return whether *docname* matches ``llm_friendly_exclude``, with the
    semantics of ``exclude_patterns``.
    """
    path = PurePath(app.env.doc2path(docname, False))
    candidates = [path.as_posix()] + [parent.as_posix() for parent in path.parents[:-1]]
    matchers = _matchers(tuple(app.config.llm_friendly_exclude))
    return any(matcher(c) for matcher in matchers for c in candidates)
