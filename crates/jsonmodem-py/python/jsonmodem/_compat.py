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
    if isinstance(value, str):
        return str.__str__(value)
    if not option & 4:
        raise TypeError("Dict key must be str")
    if value is None:
        return "null"
    if type(value) in (bool, int, float):
        return native.dumps(value).decode("ascii")
    if isinstance(value, enum.Enum):
        return key_text(value.value, option)
    if isinstance(value, int):
        return native.dumps(int.__int__(value)).decode("ascii")
    if type(value) in (datetime.datetime, datetime.date, datetime.time):
        return datetime_text(value, option)
    if type(value) is uuid.UUID:
        return str(value)
    raise TypeError("Dict key must a type serializable with OPT_NON_STR_KEYS")


class Frame:
    """An owning snapshot iterator and the output position of one container."""
    __slots__ = ("iterator", "owner", "object", "depth", "count")

    def __init__(self, iterator, owner, is_object, depth):
        self.iterator = iterator
        self.owner = owner
        self.object = is_object
        self.depth = depth
        self.count = 0


def dumps(obj, default=None, option=None, default_provided=False):
    option = 0 if option is None else option
    output = bytearray()
    frames = []
    active = set()
    value = obj
    default_depth = 0
    indent = bool(option & 1)

    while True:
        value_type = type(value)
        depth = len(frames)
        container = None
        container_limit = 254
        if value_type in (type(None), bool, int, float, str, native.Fragment):
            output.extend(native.dumps(value, option=option & 64))
        elif isinstance(value, enum.Enum):
            value = value.value
            continue
        elif not option & 256 and isinstance(value, str):
            output.extend(native.dumps(str.__str__(value)))
        elif not option & 256 and isinstance(value, int):
            output.extend(native.dumps(int.__int__(value), option=option & 64))
        elif value_type is tuple or (isinstance(value, (list, dict)) and (not option & 256 or value_type in (list, dict))):
            is_object = isinstance(value, dict)
            if is_object:
                pairs = [(key_text(key, option), item) for key, item in dict.items(value)]
                if option & 32:
                    pairs.sort(key=lambda pair: pair[0])
                iterator = iter(pairs)
            else:
                iterator = iter(tuple(list.__iter__(value) if isinstance(value, list) else value))
            container = Frame(iterator, value, is_object, depth)
        elif value_type in (datetime.datetime, datetime.date, datetime.time) and not option & 512:
            output.extend(native.dumps(datetime_text(value, option)))
        elif value_type is uuid.UUID:
            output.extend(native.dumps(str(value)))
        elif dataclasses.is_dataclass(value) and not isinstance(value, type) and not option & 2048:
            container_limit = 255
            if hasattr(value, "__dict__") and not hasattr(value_type, "__slots__"):
                fields = {key: item for key, item in vars(value).items() if not key.startswith("_")}
            else:
                fields = {field.name: getattr(value, field.name) for field in dataclasses.fields(value) if not field.name.startswith("_")}
            encoded = native._dumps_fields(fields, option, depth)
            if encoded is None:
                container = Frame(iter(fields.items()), value, True, depth)
            elif not frames:
                return encoded + b"\n" if option & 1024 else encoded
            else:
                output.extend(encoded)
        else:
            encoded = None
            if option & 16:
                from ._numpy import encode
                encoded = encode(value, option, default_provided, depth)
            if encoded is not None:
                if not frames:
                    return encoded + b"\n" if option & 1024 else encoded
                output.extend(encoded)
            else:
                if default_depth == 255:
                    raise TypeError("default serializer exceeds recursion limit")
                if not default_provided:
                    raise TypeError(f"Type is not JSON serializable: {value_type.__name__}")
                try:
                    value = default(value)
                except BaseException as error:
                    raise TypeError(f"Type is not JSON serializable: {value_type.__name__}") from error
                default_depth += 1
                continue

        if container is not None:
            # Empty lists/tuples use orjson's scalar fast case; objects count even when empty.
            if not container.object and not value:
                output.extend(b"[]")
            else:
                if depth >= container_limit or id(value) in active:
                    raise TypeError("Recursion limit reached")
                active.add(id(value))
                frames.append(container)
                output.extend(b"{" if container.object else b"[")

        default_depth = 0
        while frames:
            frame = frames[-1]
            try:
                item = next(frame.iterator)
            except StopIteration:
                frames.pop()
                active.remove(id(frame.owner))
                if indent and frame.count:
                    output.extend(b"\n" + b"  " * frame.depth)
                output.extend(b"}" if frame.object else b"]")
                continue
            if frame.count:
                output.extend(b",")
            if indent:
                output.extend(b"\n" + b"  " * (frame.depth + 1))
            frame.count += 1
            if frame.object:
                key, value = item
                output.extend(native.dumps(key))
                output.extend(b": " if indent else b":")
            else:
                value = item
            break
        else:
            if option & 1024:
                output.extend(b"\n")
            return bytes(output)
