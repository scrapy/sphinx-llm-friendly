import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

project = "sphinx_markdown_builder"
copyright = "Copyright (c) 2023-2026, Liran Funaro."
author = "Liran Funaro"
version = "0.6.11"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx_llm_friendly",
    "sphinxcontrib.httpdomain",
]

autosummary_generate = True
autoclass_content = "both"
autodoc_inherit_docstrings = True
autodoc_typehints = "description"
add_module_names = False
autodoc_member_order = "bysource"

templates_path = ["_templates"]

language = "en"
