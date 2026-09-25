=============
Release notes
=============

0.5.1 (2026-09-25)
==================

-   Fixed "unknown node type" warnings for the ``youtube``, ``vimeo`` and
    ``peertube`` directives of sphinxcontrib-youtube, now rendered as links
    to the video.

-   References with custom text no longer show the section heading when it
    only differs from that text by a leading number, e.g. a reference with
    ``Foo`` as text to a ``1. Foo`` section.

0.5.0 (2026-09-24)
==================

-   Added the ``llm_friendly_llms_full_txt_max_tokens`` setting, which logs a
    warning when ``llms-full.txt`` exceeds the given number of tokens.
    Default: ``200_000``. Set it to ``None`` to disable the check.

-   sphinx-design tabs can now be left out of the Markdown output by giving
    the ``llm-friendly-exclude`` class to their label or content, with the
    ``class-label`` or ``class-content`` option of ``tab-item``.

-   Fixed "unknown node type" warnings for the ``meta`` directive, now left
    out of the Markdown output, and for sphinx-design buttons, now rendered
    as links.

-   References in the Markdown pages no longer link to anchors, which the
    Markdown output does not have: references to the same page become plain
    text, and references to other pages link to the whole page.

    References to a section with custom text also show the section heading:
    as ``foo (see Bar)`` on the same page, and as the link title on others.

-   The Markdown output no longer includes the tables of contents of the
    ``contents`` directive, nor the section entries of toctrees.

-   Links to external documentation in signatures are now plain text, to
    reduce the size of the Markdown output.

-   When ``html_baseurl`` has a path, links in ``llms.txt`` now start with a
    slash, e.g. ``/en/latest/index.md``, so they also work when ``llms.txt``
    is served from that path.

-   Fixed the ``Source:`` lines of ``llms-full.txt`` missing the path of
    ``html_baseurl``.

0.4.0 (2026-09-24)
==================

-   For the Markdown output, the ``only`` directive now evaluates its
    expression with the ``llm`` tag instead of ``html``, e.g. use
    ``.. only:: llm`` for content to include only in the Markdown output, and
    ``.. only:: not llm`` for content to leave out of it.

-   Fixed the Markdown output of sphinx-design dropdowns and tab sets, which
    now become a rubric with their title or tab label, followed by their
    content.

0.3.0 (2026-09-24)
==================

-   The Markdown pages, ``llms.txt`` and ``llms-full.txt`` are now written by
    the ``html`` builder, next to the HTML pages, so a regular
    ``sphinx-build -b html`` produces the whole output.

    The ``llm_markdown`` and ``llm_singlemarkdown`` builders have been
    removed, and the ``dirhtml`` builder no longer writes ``llms.txt``.
    Markdown handlers for third-party nodes must now be registered with
    ``app.add_node()`` as ``llm_markdown``.

-   Deprecated the ``sphinx-llm-friendly build`` command and
    ``sphinx_llm_friendly.build()``. Use ``sphinx-build -b html`` instead.

-   Added support for the ``llm-friendly-exclude`` class, to leave content out
    of the Markdown output, e.g. with the ``container`` directive.

0.2.0 (2026-09-24)
==================

Added the ``llm_friendly_llms_full_txt_exclude`` setting, to leave documents
out of ``llms-full.txt`` while keeping their Markdown page and their
``llms.txt`` entry.

0.1.0 (2026-09-24)
==================

Initial version.
