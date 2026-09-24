from __future__ import annotations

import posixpath
from importlib.metadata import version
from typing import TYPE_CHECKING, Any

from sphinx.util.osutil import relative_uri

from ._build import build, remember_intersphinx_urls
from ._builder import MarkdownBuilder
from ._exclude import is_excluded
from ._llms_txt import write_llms_txt
from ._singlemarkdown import SingleFileMarkdownBuilder

if TYPE_CHECKING:
    from docutils import nodes
    from sphinx.application import Sphinx
    from sphinx.util.typing import ExtensionMetadata

__all__ = ["build", "setup"]

_COPY_AS_MARKDOWN_BUTTON_JS = """
(function () {
    var DEFAULT_LABEL = 'M\u2193';
    var SUCCESS_LABEL = 'Copied';
    var ERROR_LABEL = 'Error';

    function markdownPathFromCurrentPage(pathname) {
        if (pathname.endsWith('.html')) {
            return pathname.slice(0, -5) + '.md';
        }
        if (pathname.endsWith('/')) {
            return pathname + 'index.md';
        }
        var lastPart = pathname.split('/').pop() || '';
        if (!lastPart.includes('.')) {
            return pathname + '.md';
        }
        return pathname + '.md';
    }

    async function copyToClipboard(text) {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return;
        }
        var textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', 'readonly');
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
    }

    function setTemporaryLabel(button, label, previousLabel) {
        var prev = typeof previousLabel !== 'undefined' ? previousLabel : button.textContent;
        button.textContent = label;
        window.setTimeout(function () {
            button.textContent = prev;
            button.disabled = false;
        }, 1000);
    }

    async function onButtonClick(button) {
        var previousLabel = button.textContent;
        button.disabled = true;
        button.textContent = '...';
        try {
            var mdPath = markdownPathFromCurrentPage(window.location.pathname);
            var response = await fetch(mdPath, { credentials: 'same-origin' });
            if (!response.ok) {
                throw new Error('Unable to fetch markdown source');
            }
            var markdown = await response.text();
            await copyToClipboard(markdown);
            setTemporaryLabel(button, SUCCESS_LABEL, previousLabel);
        } catch (_error) {
            setTemporaryLabel(button, ERROR_LABEL, previousLabel);
        }
    }

    function addStyles() {
        var style = document.createElement('style');
        style.textContent = [
            '.scrapy-copy-as-markdown {',
            '  display: inline-block;',
            '  margin-left: 0.25rem;',
            '  border: 1px solid #c9d4de;',
            '  border-radius: 0.45rem;',
            '  background: #ffffff;',
            '  color: #233a50;',
            '  font: inherit;',
            '  font-size: 0.875rem;',
            '  line-height: 1;',
            '  padding: 0.25rem 0.25rem;',
            '  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);',
            '  cursor: pointer;',
            '}',
            '.scrapy-copy-as-markdown:hover {',
            '  background: #f3f7fb;',
            '}',
            '.scrapy-copy-as-markdown:disabled {',
            '  opacity: 0.75;',
            '  cursor: default;',
            '}',
            '.scrapy-copy-as-markdown-title-wrapper {',
            '  display: flex;',
            '  align-items: center;',
            '  justify-content: space-between;',
            '  gap: 1rem;',
            '  width: 100%;',
            '}',
            '.scrapy-copy-as-markdown-title-wrapper h1 {',
            '  margin: 0;',
            '}',
        ].join('\\n');
        document.head.appendChild(style);
    }

    function addButton() {
        if (!document.body || document.querySelector('.scrapy-copy-as-markdown')) {
            return;
        }

        addStyles();
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'scrapy-copy-as-markdown';
        button.title = 'Copy this page as Markdown';
        button.setAttribute('aria-label', 'Copy this page as Markdown');
        button.textContent = DEFAULT_LABEL;
        button.addEventListener('click', function () {
            onButtonClick(button);
        });

        var h1 = document.querySelector('#main h1') || document.querySelector('h1');
        if (h1 && h1.parentNode) {
            var parent = h1.parentNode;
            var wrapper = document.createElement('div');
            wrapper.className = 'scrapy-copy-as-markdown-title-wrapper';
            parent.replaceChild(wrapper, h1);
            wrapper.appendChild(h1);
            wrapper.appendChild(button);
        } else {
            // fallback: insert at top of body but keep within the first container
            var container = document.body.firstElementChild || document.body;
            container.insertBefore(button, container.firstChild);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addButton);
    } else {
        addButton();
    }
})();
"""


def _on_builder_inited(app: Sphinx) -> None:
    if isinstance(app.builder, MarkdownBuilder):
        app.config.exclude_patterns = [
            *app.config.exclude_patterns,
            *app.config.llm_friendly_exclude,
        ]
    elif app.builder.format == "html":
        app.add_js_file(None, body=_COPY_AS_MARKDOWN_BUTTON_JS)


def _add_markdown_alternate_link(
    app: Sphinx,
    pagename: str,
    templatename: str,
    context: dict[str, Any],
    doctree: nodes.document | None,
) -> None:
    if (
        app.builder.format != "html"
        or pagename not in app.env.found_docs
        or is_excluded(app, pagename)
    ):
        return
    html_uri = app.builder.get_target_uri(pagename)
    md_uri = f"{posixpath.splitext(html_uri)[0]}.md"
    href = relative_uri(html_uri, md_uri)
    context["metatags"] = context.get("metatags", "") + (
        f'\n<link rel="alternate" type="text/markdown" href="{href}">'
    )


def _on_build_finished(app: Sphinx, exception: Exception | None) -> None:
    if exception is None and app.builder.name in {"html", "dirhtml"}:
        write_llms_txt(app)


def setup(app: Sphinx) -> ExtensionMetadata:
    app.add_builder(MarkdownBuilder)
    app.add_builder(SingleFileMarkdownBuilder)

    app.add_config_value("llm_friendly_exclude", [], "env", types=frozenset({list}))
    app.add_config_value(
        "llm_friendly_llms_txt_summary",
        None,
        "html",
        types=frozenset({str, type(None)}),
    )
    app.add_config_value(
        "llm_friendly_llms_txt_toctree_only", False, "html", types=frozenset({bool})
    )

    app.connect("builder-inited", _on_builder_inited)
    app.connect("html-page-context", _add_markdown_alternate_link)
    app.connect("build-finished", _on_build_finished)
    app.connect("build-finished", remember_intersphinx_urls)

    return {
        "version": version("sphinx-llm-friendly"),
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
