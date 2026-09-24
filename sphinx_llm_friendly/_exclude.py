from __future__ import annotations

from functools import cache
from pathlib import PurePath
from typing import TYPE_CHECKING

from sphinx.util.matching import compile_matchers

if TYPE_CHECKING:
    from collections.abc import Callable

    from sphinx.environment import BuildEnvironment


@cache
def _matchers(patterns: tuple[str, ...]) -> list[Callable[[str], bool]]:
    return compile_matchers(patterns)  # type: ignore[return-value]


def is_excluded(
    env: BuildEnvironment, docname: str, patterns: list[str] | None = None
) -> bool:
    """Return whether *docname* matches *patterns*, ``llm_friendly_exclude``
    by default, with the semantics of ``exclude_patterns``.
    """
    path = PurePath(env.doc2path(docname, False))
    candidates = [path.as_posix()] + [parent.as_posix() for parent in path.parents[:-1]]
    matchers = _matchers(
        tuple(env.config.llm_friendly_exclude if patterns is None else patterns)
    )
    return any(matcher(c) for matcher in matchers for c in candidates)
