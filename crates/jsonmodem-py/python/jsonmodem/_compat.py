"""Direct output for Python objects that need callbacks or optional type support."""

import dataclasses
import datetime
import enum
import uuid

from . import _jsonmodem as native


def datetime_text(value, option):
    """Format RFC 3339 wall time with orjson's minute-resolution UTC offset."""
    if isinstance(value, datetime.datetime):
        text = f"{value.year:04}-{value.month:02}-{value.day:02}T"
    elif isinstance(value, datetime.date):
        return f"{value.year:04}-{value.month:02}-{value.day:02}"
    else:
        if value.tzinfo is not None:
            raise TypeError("datetime's timezone library is not supported: use datetime.timezone.utc, pendulum, pytz, or dateutil")
        text = ""
    text += f"{value.hour:02}:{value.minute:02}:{value.second:02}"
    if value.microsecond and not option & 8:
        text += f".{value.microsecond:06}"
    if isinstance(value, datetime.datetime):
        tz = value.tzinfo
        if tz is None:
            offset = datetime.timedelta(0) if option & 2 else None
        elif hasattr(tz, "normalize") and not hasattr(tz, "convert"):
            offset = tz.normalize(value).utcoffset()
        else:
            offset = value.utcoffset()
        if offset is not None:
            seconds = offset.days * 86400 + offset.seconds
            minutes = (abs(seconds) + 30) // 60
            if not minutes and option & 128:
                text += "Z"
            else:
                text += f"{'-' if seconds < 0 else '+'}{minutes // 60:02}:{minutes % 60:02}"
    return text


def key_text(value, option):
    if type(value) is str:
        return value
    if not option & 4:
        raise TypeError("Dict key must be str")
    if isinstance(value, str):
        return str.__str__(value)
    if value is None:
        return "null"
    if type(value) in (bool, int, float):
        if type(value) is int and not -(2**63) <= value <= 2**64 - 1:
            # CPython supplies the same unsigned-conversion cause for key errors.
            try:
                value.to_bytes(8, "little")
            except OverflowError as cause:
                raise TypeError("Dict integer key must be within 64-bit range") from cause
        return native.dumps(value).decode("ascii")
    if isinstance(value, enum.Enum):
        return key_text(value.value, option)
    if isinstance(value, int):
        return key_text(int.__int__(value), option)
    if type(value) in (datetime.datetime, datetime.date, datetime.time):
        return datetime_text(value, option)
    if type(value) is uuid.UUID:
        return str(value)
    raise TypeError("Dict key must a type serializable with OPT_NON_STR_KEYS")


def special(value, option, default_provided, depth):
    """Return normalized text or encoded NumPy bytes, or leave the value to default."""
    value_type = type(value)
    if value_type in (datetime.datetime, datetime.date, datetime.time) and not option & 512:
        return False, datetime_text(value, option)
    if value_type is uuid.UUID:
        return False, str(value)
    if option & 16:
        from ._numpy import encode

        encoded = encode(value, option, default_provided, depth)
        if encoded is not None:
            return True, encoded
    return None


# Keep standard types and operations alive without importing modules for each call.
# The tuple order matches ObjectEncoder::new in compat/objects.rs.
_ENCODER_HELPERS = (
    enum.Enum, dataclasses.fields, key_text, special,
    datetime.datetime, datetime.date, datetime.time, uuid.UUID,
    str.__str__, int.__int__, getattr, type.__dict__["__dict__"].__get__,
)


def dumps(obj, default=None, option=None, default_provided=False):
    return native._dumps_objects(
        obj, default, 0 if option is None else option, default_provided, _ENCODER_HELPERS
    )
