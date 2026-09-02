"""Complete-document JSON operations and incremental parsing."""

from json import JSONDecodeError

from . import _jsonmodem as _native
from ._compat import dumps as _dumps_fallback

JsonModem = _native.JsonModem
JsonModemEvents = _native.JsonModemEvents
PathView = _native.PathView
StringPayload = _native.StringPayload
JsonModemValues = _native.JsonModemValues
JsonModemValueView = _native.JsonModemValueView
ParserOptions = _native.ParserOptions
DecodeMode = _native.DecodeMode
JsonModemSyntaxError = _native.JsonModemSyntaxError
JsonModemStateError = _native.JsonModemStateError
loads = _native.loads
dumps = _native.dumps
Fragment = _native.Fragment
JSONEncodeError = TypeError

OPT_INDENT_2 = 1
OPT_NAIVE_UTC = 2
OPT_NON_STR_KEYS = 4
OPT_OMIT_MICROSECONDS = 8
OPT_SERIALIZE_NUMPY = 16
OPT_SORT_KEYS = 32
OPT_STRICT_INTEGER = 64
OPT_UTC_Z = 128
OPT_PASSTHROUGH_SUBCLASS = 256
OPT_PASSTHROUGH_DATETIME = 512
OPT_APPEND_NEWLINE = 1024
OPT_PASSTHROUGH_DATACLASS = 2048
OPT_SERIALIZE_DATACLASS = 0
OPT_SERIALIZE_UUID = 0

__all__ = [
    "JsonModem", "JsonModemEvents", "PathView", "StringPayload", "JsonModemValues",
    "JsonModemValueView", "ParserOptions", "DecodeMode", "JsonModemSyntaxError",
    "JsonModemStateError", "JSONDecodeError", "JSONEncodeError", "Fragment",
    "loads", "dumps", "OPT_APPEND_NEWLINE", "OPT_INDENT_2", "OPT_NAIVE_UTC",
    "OPT_NON_STR_KEYS", "OPT_OMIT_MICROSECONDS", "OPT_PASSTHROUGH_DATACLASS",
    "OPT_PASSTHROUGH_DATETIME", "OPT_PASSTHROUGH_SUBCLASS", "OPT_SERIALIZE_DATACLASS",
    "OPT_SERIALIZE_NUMPY", "OPT_SERIALIZE_UUID", "OPT_SORT_KEYS", "OPT_STRICT_INTEGER",
    "OPT_UTC_Z",
]

__version__ = getattr(_native, "__version__", "0.0.0")
