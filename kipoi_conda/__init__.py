from __future__ import absolute_import

__author__ = 'Kipoi team'
__email__ = 'thorsten.beier@embl.de'

from ._version import __version__

from .utils import *
from .utils import _call_and_parse, _call_command, _call_conda, _call_pip

from .dependencies import Dependencies