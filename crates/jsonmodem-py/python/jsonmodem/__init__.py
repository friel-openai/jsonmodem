"""Complete-document JSON operations and incremental parsing."""

from __future__ import annotations

import dataclasses as _dataclasses
import datetime as _datetime
import json as _json
import math as _math
import secrets as _secrets
import uuid as _uuid
from typing import Any as _Any, Callable as _Callable

from . import _jsonmodem as _native

JsonModem = _native.JsonModem
PathView = _native.PathView
StringPayload = _native.StringPayload
JsonModemValues = _native.JsonModemValues
JsonModemValueView = _native.JsonModemValueView
ParserOptions = _native.ParserOptions
DecodeMode = _native.DecodeMode
JsonModemSyntaxError = _native.JsonModemSyntaxError
JsonModemStateError = _native.JsonModemStateError
loads = _native.loads

JSONDecodeError = _json.JSONDecodeError
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

_SUPPORTED_OPTIONS = (
    OPT_INDENT_2
    | OPT_NAIVE_UTC
    | OPT_NON_STR_KEYS
    | OPT_OMIT_MICROSECONDS
    | OPT_SERIALIZE_NUMPY
    | OPT_SORT_KEYS
    | OPT_STRICT_INTEGER
    | OPT_UTC_Z
    | OPT_PASSTHROUGH_SUBCLASS
    | OPT_PASSTHROUGH_DATETIME
    | OPT_APPEND_NEWLINE
    | OPT_PASSTHROUGH_DATACLASS
)
_MAX_DEPTH = 256


class Fragment:
    """A validated JSON value inserted without reformatting."""

    __slots__ = ("_value",)

    def __init__(self, value: str | bytes | bytearray | memoryview) -> None:
        if not isinstance(value, (str, bytes, bytearray, memoryview)):
            raise JSONEncodeError("Fragment requires str or bytes-like input")
        # Validate the snapshot, not an object whose conversion can change it.
        loads(value)
        raw = str.encode(value) if isinstance(value, str) else bytes(value)
        loads(raw)
        self._value = raw

    @property
    def value(self) -> bytes:
        return self._value


def _datetime_text(value: _datetime.date | _datetime.time, option: int) -> str:
    if isinstance(value, _datetime.datetime) and value.tzinfo is None and option & OPT_NAIVE_UTC:
        value = value.replace(tzinfo=_datetime.timezone.utc)
    timespec = "seconds" if option & OPT_OMIT_MICROSECONDS else "auto"
    if isinstance(value, (_datetime.datetime, _datetime.time)):
        text = value.isoformat(timespec=timespec)
    else:
        text = value.isoformat()
    if option & OPT_UTC_Z and text.endswith("+00:00"):
        text = text[:-6] + "Z"
    return text


def _non_str_key(key: _Any) -> str:
    if key is None:
        return "null"
    if key is True:
        return "true"
    if key is False:
        return "false"
    if isinstance(key, (int, float, _uuid.UUID)):
        return str(key)
    if isinstance(key, (_datetime.date, _datetime.time)):
        return key.isoformat()
    raise JSONEncodeError("Dict key must be str when OPT_NON_STR_KEYS is not set")


def _prepare(
    value: _Any,
    option: int,
    default: _Callable[[_Any], _Any] | None,
    fragments: list[tuple[str, bytes]],
    active: set[int],
    depth: int,
) -> _Any:
    if depth > _MAX_DEPTH:
        raise JSONEncodeError(f"recursion depth exceeded: maximum is {_MAX_DEPTH}")
    if value is None or type(value) in (bool, str):
        return value
    if type(value) is int:
        if option & OPT_STRICT_INTEGER and not -(2**53) + 1 <= value <= 2**53 - 1:
            raise JSONEncodeError("Integer exceeds 53-bit range")
        if not -(2**63) <= value < 2**64:
            raise JSONEncodeError("Integer exceeds 64-bit range")
        return value
    if type(value) is float:
        return value if _math.isfinite(value) else None
    if isinstance(value, Fragment):
        raw = value.value
        if type(raw) is not bytes:
            raise JSONEncodeError("Fragment value must be immutable bytes")
        loads(raw)
        marker = f"__jsonmodem_fragment_{_secrets.token_hex(24)}__"
        fragments.append((marker, raw))
        return marker

    if (
        option & OPT_PASSTHROUGH_SUBCLASS
        and type(value) not in (str, int, float, list, tuple, dict)
        and isinstance(value, (str, int, float, list, tuple, dict))
    ):
        return _use_default(value, option, default, fragments, active, depth)
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return _prepare(int(value), option, default, fragments, active, depth)
    if isinstance(value, float):
        return _prepare(float(value), option, default, fragments, active, depth)

    identity = id(value)
    if isinstance(value, (list, tuple, dict)):
        if identity in active:
            raise JSONEncodeError("Recursion limit reached")
        active.add(identity)
        try:
            if isinstance(value, dict):
                result = {}
                for key, item in value.items():
                    if type(key) is not str:
                        if not option & OPT_NON_STR_KEYS:
                            raise JSONEncodeError("Dict key must be str")
                        key = _non_str_key(key)
                    if key in result:
                        raise JSONEncodeError("converted dictionary keys collide")
                    result[key] = _prepare(item, option, default, fragments, active, depth + 1)
                return result
            return [_prepare(item, option, default, fragments, active, depth + 1) for item in value]
        finally:
            active.remove(identity)

    if isinstance(value, (_datetime.datetime, _datetime.date, _datetime.time)):
        if option & OPT_PASSTHROUGH_DATETIME:
            return _use_default(value, option, default, fragments, active, depth)
        return _datetime_text(value, option)
    if isinstance(value, _uuid.UUID):
        return str(value)
    if _dataclasses.is_dataclass(value) and not isinstance(value, type):
        if option & OPT_PASSTHROUGH_DATACLASS:
            return _use_default(value, option, default, fragments, active, depth)
        return _prepare(
            {field.name: getattr(value, field.name) for field in _dataclasses.fields(value)},
            option,
            default,
            fragments,
            active,
            depth + 1,
        )
    if option & OPT_SERIALIZE_NUMPY:
        if type(value).__module__.startswith("numpy"):
            converted = value.tolist() if hasattr(value, "tolist") else value.item()
            return _prepare(converted, option, default, fragments, active, depth + 1)
    return _use_default(value, option, default, fragments, active, depth)


def _use_default(
    value: _Any,
    option: int,
    default: _Callable[[_Any], _Any] | None,
    fragments: list[tuple[str, bytes]],
    active: set[int],
    depth: int,
) -> _Any:
    if default is None:
        raise JSONEncodeError(f"Type is not JSON serializable: {type(value).__name__}")
    return _prepare(default(value), option, default, fragments, active, depth + 1)


def _dumps_fallback(
    obj: _Any,
    /,
    default: _Callable[[_Any], _Any] | None = None,
    option: int | None = None,
) -> bytes:
    """Serialize an object using the commonly used ``orjson.dumps`` contract."""

    option = 0 if option is None else option
    if type(option) is not int:
        raise JSONEncodeError("option must be an integer")
    if option & ~_SUPPORTED_OPTIONS:
        raise JSONEncodeError(f"unsupported option bits: {option & ~_SUPPORTED_OPTIONS}")
    if default is not None and not callable(default):
        raise JSONEncodeError("default must be callable")

    fragments: list[tuple[str, bytes]] = []
    try:
        prepared = _prepare(obj, option, default, fragments, set(), 0)
        text = _json.dumps(
            prepared,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=bool(option & OPT_SORT_KEYS),
            indent=2 if option & OPT_INDENT_2 else None,
            separators=None if option & OPT_INDENT_2 else (",", ":"),
        ).encode()
    except Exception as error:
        raise JSONEncodeError(str(error)) from error
    for marker, fragment in fragments:
        encoded = _json.dumps(marker).encode()
        if text.count(encoded) != 1:
            raise JSONEncodeError("fragment placeholder collision")
        text = text.replace(encoded, fragment, 1)
    if fragments:
        # Fragments can combine into a document deeper than any one fragment.
        # Recheck after substitution, including deliberately modified instances.
        try:
            loads(text)
        except JSONDecodeError as error:
            raise JSONEncodeError(str(error)) from error
    if option & OPT_APPEND_NEWLINE:
        text += b"\n"
    return text

dumps = _native.dumps

__all__ = [
    "JsonModem",
    "PathView",
    "StringPayload",
    "JsonModemValues",
    "JsonModemValueView",
    "ParserOptions",
    "DecodeMode",
    "JsonModemSyntaxError",
    "JsonModemStateError",
    "JSONDecodeError",
    "JSONEncodeError",
    "Fragment",
    "loads",
    "dumps",
    "OPT_APPEND_NEWLINE",
    "OPT_INDENT_2",
    "OPT_NAIVE_UTC",
    "OPT_NON_STR_KEYS",
    "OPT_OMIT_MICROSECONDS",
    "OPT_PASSTHROUGH_DATACLASS",
    "OPT_PASSTHROUGH_DATETIME",
    "OPT_PASSTHROUGH_SUBCLASS",
    "OPT_SERIALIZE_DATACLASS",
    "OPT_SERIALIZE_NUMPY",
    "OPT_SERIALIZE_UUID",
    "OPT_SORT_KEYS",
    "OPT_STRICT_INTEGER",
    "OPT_UTC_Z",
]

__version__ = getattr(_native, "__version__", "0.0.0")
