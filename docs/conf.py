# -*- coding: utf-8 -*-
# sphinx config

project = u'amitools'
copyright = u'2019, Christian Vogelgsang'
author = u'Christian Vogelgsang'

version = u'0.3'
release = u'0.3.0'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
]
templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
language = 'en'
exclude_patterns = []
pygments_style = None

# -- Options for HTML output -------------------------------------------------
html_theme = 'alabaster'
#html_static_path = ['_static']

# -- Extension configuration -------------------------------------------------
intersphinx_mapping = {'https://docs.python.org/': None}
todo_include_todos = True
