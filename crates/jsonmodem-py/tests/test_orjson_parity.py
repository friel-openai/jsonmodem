"""Public API behavior checked against the pinned release oracle."""
import math
import dataclasses
import datetime
import enum
import random
import struct
import uuid
import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")


@pytest.mark.parametrize("text", [str(-(2**63)-1), str(2**64), str(2**100), "9"*309])
def test_integer_overflow_matches_orjson(text):
    try:
        expected = orjson.loads(text)
    except orjson.JSONDecodeError:
        with pytest.raises(jsonmodem.JSONDecodeError):
            jsonmodem.loads(text)
    else:
        actual = jsonmodem.loads(text)
        assert type(actual) is type(expected)
        assert actual == expected


@pytest.mark.parametrize("value", [None, 0, [], {}, 1.2])
def test_unsupported_loads_input(value):
    with pytest.raises(jsonmodem.JSONDecodeError):
        jsonmodem.loads(value)


@pytest.mark.parametrize("depth", [254,255,256,1024,1025])
def test_decode_depth(depth):
    text = "["*depth + "0" + "]"*depth
    try:
        orjson.loads(text)
    except orjson.JSONDecodeError:
        with pytest.raises(jsonmodem.JSONDecodeError):
            jsonmodem.loads(text)
    else:
        actual = jsonmodem.loads(text)
        for _ in range(depth):
            actual = actual[0]
        assert actual == 0


@pytest.mark.parametrize("depth", [253,254,255])
@pytest.mark.parametrize("leaf", [0, [], (), {}])
def test_encode_depth(depth, leaf):
    value = leaf
    for _ in range(depth): value = [value]
    try:
        expected = orjson.dumps(value)
    except orjson.JSONEncodeError:
        with pytest.raises(jsonmodem.JSONEncodeError): jsonmodem.dumps(value)
    else:
        assert jsonmodem.dumps(value) == expected


@pytest.mark.parametrize("value", [1e20,1e-6,1e-7,1e16,1e15,-0.0,math.inf,1.2345678901234567])
def test_float_bytes(value):
    assert jsonmodem.dumps(value) == orjson.dumps(value)


@pytest.mark.parametrize("raw", [b"", b"invalid", b"\xff", b"[0,]", '"hello"'])
def test_fragment_is_raw_output(raw):
    assert jsonmodem.dumps([jsonmodem.Fragment(raw)]) == orjson.dumps([orjson.Fragment(raw)])


@pytest.mark.parametrize("option", [orjson.OPT_NON_STR_KEYS, orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS])
def test_converted_key_collisions_preserved(option):
    value = {"1": True, 1: False}
    assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)


def test_unused_noncallable_default():
    assert jsonmodem.dumps([1], default=42) == orjson.dumps([1], default=42)


def test_float_bits_differential():
    random_source = random.Random(391)
    values = [struct.unpack("d", random_source.getrandbits(64).to_bytes(8, "little"))[0] for _ in range(10000)]
    assert jsonmodem.dumps(values) == orjson.dumps(values)


@pytest.mark.parametrize("option", [0, 1, 2, 8, 32, 128, 256, 512, 1024, 2048])
def test_objects_and_options(option):
    @dataclasses.dataclass
    class Record:
        z: int
        a: dict
        _private: int = 7

    class Integer(int):
        def __int__(self):
            raise AssertionError("must not call an overridden conversion")

    class Text(str):
        def __str__(self):
            raise AssertionError("must not call an overridden conversion")

    class Choice(enum.Enum):
        A = "a"

    values = [Record(2, {"z": 1, "a": 2}), Integer(3), Text("text"), Choice.A,
              datetime.datetime(2001, 2, 3, 4, 5, 6, 123000),
              datetime.date(7, 2, 3), datetime.time(4, 5, 6, 120000),
              uuid.UUID(int=42)]
    default = lambda obj: type(obj).__name__
    assert jsonmodem.dumps(values, option=option, default=default) == orjson.dumps(values, option=option, default=default)


@pytest.mark.parametrize("default", [None, 7])
def test_default_error_cause(default):
    causes = []
    for module in (jsonmodem, orjson):
        with pytest.raises(TypeError) as error:
            module.dumps(object(), default=default)
        causes.append(type(error.value.__cause__))
    assert causes[0] is causes[1]


def test_builtin_bytesio_and_memoryview_formats():
    import io
    data = b"[1,2,3] "
    for value in (io.BytesIO(data).getbuffer(), memoryview(data).cast("I")):
        assert jsonmodem.loads(value) == orjson.loads(value)


@pytest.mark.parametrize("depth", [252, 253])
def test_dataclass_snapshot_depth_and_indentation(depth):
    @dataclasses.dataclass
    class Record:
        z: int = 1
        a: dict = dataclasses.field(default_factory=lambda: {"z": 2, "a": 3})

    value = Record()
    for _ in range(depth):
        value = [value]
    option = orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
    try:
        expected = orjson.dumps(value, option=option)
    except TypeError:
        with pytest.raises(TypeError):
            jsonmodem.dumps(value, option=option)
    else:
        assert jsonmodem.dumps(value, option=option) == expected


def test_dataclass_at_depth_boundary():
    @dataclasses.dataclass
    class Record:
        value: object

    leaf = Record(0)
    value = leaf
    for _ in range(254):
        value = [value]
    assert jsonmodem.dumps(value) == orjson.dumps(value)
    # The reference's eight-bit counter wraps on the next container. Stay bounded.
    leaf.value = {"a": 0}
    with pytest.raises(TypeError, match="Recursion"):
        jsonmodem.dumps(value)


def test_dataclass_snapshot_cycle_and_callback():
    @dataclasses.dataclass
    class Record:
        value: object

    recursive = Record(None)
    recursive.value = recursive
    with pytest.raises(TypeError):
        jsonmodem.dumps(recursive)
    value = [Record(object())]
    default = lambda _: "converted"
    assert jsonmodem.dumps(value, default=default) == orjson.dumps(value, default=default)


def test_primitive_keys_ignore_strict_integer():
    value = {2**64 - 1: "integer", None: 0, float("nan"): 1, "null": 2}
    option = orjson.OPT_NON_STR_KEYS | orjson.OPT_STRICT_INTEGER
    assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)
