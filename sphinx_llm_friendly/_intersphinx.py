from __future__ import annotations

import concurrent.futures
import re
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

_URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]{}\"']+")


def _matching_base_url(url: str, base_urls: Iterable[str]) -> str | None:
    for base_url in base_urls:
        if url.startswith(base_url):
            return base_url
    return None


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


def _rewrite_url_to_markdown(
    url: str, enabled_base_urls: set[str], base_urls: Iterable[str]
) -> str:
    base_url = _matching_base_url(url, base_urls)
    if not base_url or base_url not in enabled_base_urls:
        return url
    parts = urlsplit(url)
    if not parts.path.endswith(".html"):
        return url
    return urlunsplit(parts._replace(path=f"{parts.path[:-5]}.md"))


def rewrite_intersphinx_links(files: Iterable[Path], site_urls: Iterable[str]) -> None:
    """Rewrite links to ``.html`` pages in *files* into links to their ``.md``
    counterpart, for the sites in *site_urls* that serve Markdown.
    """
    base_urls = sorted(site_urls, key=len, reverse=True)
    file_contents: dict[Path, str] = {}
    candidate_base_urls: set[str] = set()
    for file in files:
        content = file.read_text(encoding="utf-8")
        file_contents[file] = content
        for match in _URL_PATTERN.finditer(content):
            url = match.group(0)
            if ".html" not in url:
                continue
            base_url = _matching_base_url(url, base_urls)
            if base_url is not None:
                candidate_base_urls.add(base_url)

    if not candidate_base_urls:
        return

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(8, len(candidate_base_urls))
    ) as executor:
        availability = {
            base_url: executor.submit(_supports_markdown, base_url)
            for base_url in candidate_base_urls
        }
        enabled_base_urls = {
            base_url for base_url, future in availability.items() if future.result()
        }

    if not enabled_base_urls:
        return

    for file, content in file_contents.items():
        rewritten = _URL_PATTERN.sub(
            lambda match: _rewrite_url_to_markdown(
                match.group(0), enabled_base_urls, base_urls
            ),
            content,
        )
        if rewritten != content:
            file.write_text(rewritten, encoding="utf-8")
