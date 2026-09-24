===================
sphinx-llm-friendly
===================

`Sphinx <https://www.sphinx-doc.org/>`_ extension that makes documentation
LLM-friendly:

-   A Markdown version of every page, next to its HTML version.

-   `llms.txt <https://llmstxt.org/>`_, with a link to the Markdown version of
    every page.

-   ``llms-full.txt``, with the Markdown version of all pages.

-   HTML pages point to their Markdown version with a ``<link
    rel="alternate" type="text/markdown">`` tag, and get a button to copy
    their Markdown version.

Setup
=====

#.  Install it:

    .. code-block:: shell

        pip install sphinx-llm-friendly

#.  Add it to ``extensions`` in ``conf.py``:

    .. code-block:: python

        extensions = [
            # …
            "sphinx_llm_friendly",
        ]

#.  Build your documentation with the ``html`` builder:

    .. code-block:: shell

        sphinx-build -b html docs docs/_build/html

    The Markdown pages, ``llms.txt`` and ``llms-full.txt`` are written next to
    the HTML pages. In the Markdown output, links to sites from
    ``intersphinx_mapping`` that serve Markdown point to the Markdown version
    of their pages.

Configuration
=============

``llm_friendly_exclude``
    List of patterns, with the syntax of ``exclude_patterns``, of documents to
    leave out of the Markdown output and ``llms.txt``. Default: ``[]``.

``llm_friendly_llms_full_txt_exclude``
    List of patterns, with the syntax of ``exclude_patterns``, of documents to
    leave out of ``llms-full.txt`` only. Default: ``[]``.

``llm_friendly_llms_txt_summary``
    Summary for ``llms.txt``. Default: the first paragraph of the root
    document.

``llm_friendly_llms_txt_toctree_only``
    If ``True``, ``llms.txt`` only lists documents reachable through toctrees
    from the root document. Default: ``False``.

To leave content out of the Markdown output, give it the
``llm-friendly-exclude`` class, e.g. with the ``container`` directive.

Nodes from third-party extensions that are still in the doctree when HTML is
written need Markdown handlers, registered with ``app.add_node()`` as
``llm_markdown``.
