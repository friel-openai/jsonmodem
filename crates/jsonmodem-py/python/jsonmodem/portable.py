"""The jsonmodem API without optional Python encoding acceleration.

This selection applies to each call. It does not change another caller's
configuration or disable existing native code in jsonmodem and its dependencies.
"""

from . import *
from . import __all__ as __all__, __version__ as __version__
from ._jsonmodem import _dumps_portable as dumps
