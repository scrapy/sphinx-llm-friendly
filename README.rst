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

#.  Build your documentation:

    .. code-block:: shell

        sphinx-llm-friendly build docs docs/_build

    The output is in ``docs/_build/all``.

    It runs the ``html``, ``llm_markdown`` and ``llm_singlemarkdown`` builders
    in parallel, into subdirectories of ``docs/_build``, and merges their
    output. In the Markdown output, links to sites from ``intersphinx_mapping``
    that serve Markdown point to the Markdown version of their pages.

    From Python, call ``sphinx_llm_friendly.build(source_dir, build_dir)``,
    which returns the output directory.

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

Nodes from third-party extensions need Markdown handlers, registered with
``app.add_node()`` for the ``llm_markdown`` and ``llm_singlemarkdown``
builders.
