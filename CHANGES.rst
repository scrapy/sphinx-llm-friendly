=============
Release notes
=============

0.3.0 (unreleased)
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
