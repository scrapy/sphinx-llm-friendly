from __future__ import annotations

import concurrent.futures
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from sphinx.application import Sphinx

# Set at builder-inited, before parallel write workers are forked.
_markdown_pages: set[str] = set()


def _supports_markdown(base_url: str) -> bool:
    probe_url = f"{base_url.rstrip('/')}/index.md"
    headers = {"User-Agent": "sphinx-llm-friendly"}
    for method in ("HEAD", "GET"):
        request = Request(probe_url, headers=headers, method=method)  # noqa: S310
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310
                status = int(response.status)
                return HTTPStatus.OK <= status < HTTPStatus.BAD_REQUEST
        except HTTPError as error:
            if method == "HEAD" and error.code in {
                HTTPStatus.METHOD_NOT_ALLOWED,
                HTTPStatus.NOT_IMPLEMENTED,
            }:
                continue
            return False
        except URLError:
            return False
    return False


def find_markdown_sites(app: Sphinx) -> None:
    """Find the pages of the sites of ``intersphinx_mapping`` that serve
    Markdown, for :func:`to_markdown_url`.
    """
    mapping = getattr(app.config, "intersphinx_mapping", {})
    urls = {name: uri for name, (uri, _inventories) in mapping.values()}
    _markdown_pages.clear()
    if not urls:
        return
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(8, len(urls))
    ) as executor:
        supported = dict(
            zip(urls, executor.map(_supports_markdown, urls.values()), strict=False)
        )
    inventories = getattr(app.env, "intersphinx_named_inventory", {})
    _markdown_pages.update(
        # Sphinx 7 inventory items are (project, version, uri, display name).
        getattr(item, "uri", None) or item[2]
        for name, inventory in inventories.items()
        if supported.get(name)
        for item in inventory.get("std:doc", {}).values()
    )


def to_markdown_url(url: str) -> str:
    """Return the URL of the Markdown version of *url* if it points to a page
    of a site found by :func:`find_markdown_sites`, or *url* otherwise.
    """
    parts = urlsplit(url)
    page = urlunsplit(parts._replace(fragment=""))
    if page not in _markdown_pages or not parts.path.endswith(".html"):
        return url
    return urlunsplit(parts._replace(path=f"{parts.path[:-5]}.md"))
