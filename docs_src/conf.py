# Sphinx Configuration

import logging
import sys
from datetime import datetime
from pathlib import Path

from sphinx.ext.autodoc import Documenter
from sphinx.util.docstrings import prepare_docstring
from sphinx.util.inspect import getdoc

project_root = Path(__file__).resolve().parents[1]
docs_src_path = project_root.joinpath('docs_src')
sys.path.append(project_root.as_posix())
sys.path.append(docs_src_path.joinpath('ext').as_posix())
from requests_client.__version__ import __author__, __version__

project = 'Requests Client'
release = __version__
author = __author__
copyright = '{}, {}'.format(datetime.now().strftime('%Y'), author)

extensions = ['sphinx.ext.intersphinx', 'sphinx.ext.autodoc', 'sphinx.ext.viewcode', 'show_on_github']

# Extension options
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'requests': ('https://requests.readthedocs.io/en/master/', None),
}
viewcode_follow_imported_members = False
show_on_github_user = 'dskrypa'
show_on_github_repo = project_root.name

templates_path = [docs_src_path.joinpath('templates').as_posix()]
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_theme_options = {'sticky_navigation': True}

html_static_path = [docs_src_path.joinpath('static').as_posix()]


def get_doc(self, encoding=None, ignore=1):
    """This patch prevents autodata object instances from having the docstrings of their classes"""
    docstring = getdoc(self.object, self.get_attr, self.env.config.autodoc_inherit_docstrings)
    obj_type_doc = getattr(type(self.object), '__doc__', None)
    if docstring == obj_type_doc:
        docstring = None
    if docstring:
        tab_width = self.directive.state.document.settings.tab_width
        return [prepare_docstring(docstring, ignore, tab_width)]
    return []


Documenter.get_doc = get_doc

logging.basicConfig(level=logging.INFO, format='%(message)s')
