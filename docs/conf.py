# -*- coding: utf-8 -*-
# sphinx config

from importlib.metadata import version

project = "amitools"
copyright = "2020-23, Christian Vogelgsang"
author = "Christian Vogelgsang"

release = version("amitools")
version = ".".join(release.split(".")[:2])

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.todo",
]
templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
language = "en"
exclude_patterns = []
pygments_style = None

# -- Options for HTML output -------------------------------------------------
html_theme = "alabaster"
# html_static_path = ['_static']

# -- Extension configuration -------------------------------------------------
intersphinx_mapping = {"https://docs.python.org/": None}
todo_include_todos = True
