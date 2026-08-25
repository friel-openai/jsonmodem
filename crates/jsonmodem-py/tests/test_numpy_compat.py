"""NumPy snapshots preserve dtype precision without creating Python value trees."""

import sys

import pytest
import jsonmodem
from jsonmodem import _jsonmodem as native

np = pytest.importorskip("numpy")


@pytest.mark.parametrize("dtype, expected", [
    ("float16", b"[0.099975586,0.19995117]"),
    ("float32", b"[0.1,0.2]"),
    ("float64", b"[0.1,0.2]"),
])
def test_float_precision(dtype, expected):
    assert jsonmodem.dumps(np.array([0.1, 0.2], dtype=dtype), option=16) == expected


@pytest.mark.parametrize("dtype", ["bool", "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64", "float16", "float32", "float64"])
@pytest.mark.parametrize("option", [16, 17, 16 | 64 | 1024])
def test_array_and_scalar_oracle(dtype, option):
    orjson = pytest.importorskip("orjson")
    array = np.arange(24).reshape(2, 3, 4).astype(dtype)
    for value in (array, array[0, 0, 0], {"array": array}):
        assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)


@pytest.mark.parametrize("unit", ["Y", "M", "W", "D", "h", "m", "s", "ms", "us", "ns"])
def test_datetime_units(unit):
    orjson = pytest.importorskip("orjson")
    value = np.array([0, 1, 100], dtype=f"datetime64[{unit}]")
    for option in (16, 16 | 2 | 128, 16 | 8):
        assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)


@pytest.mark.parametrize("shape", [(0,), (2, 0), (2, 3, 0), (2, 0, 3)])
def test_empty_dimensions(shape):
    orjson = pytest.importorskip("orjson")
    value = np.empty(shape)
    for option in (16, 17):
        assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)


def test_layout_and_default():
    array = np.arange(12).reshape(3, 4)[:, ::2]
    with pytest.raises(TypeError, match="C contiguous"):
        jsonmodem.dumps(array, option=16)
    assert jsonmodem.dumps(array, option=16, default=lambda a: a.tolist()) == b"[[0,2],[4,6],[8,10]]"
    endian = ">" if sys.byteorder == "little" else "<"
    with pytest.raises(TypeError, match="native-endianness"):
        jsonmodem.dumps(np.array([1], dtype=endian + "i8"), option=16)


def test_checked_datetime_arithmetic():
    # Do not invoke the oracle on descriptors that can fault its native formatter.
    with pytest.raises(TypeError, match="multipliers"):
        jsonmodem.dumps(np.array([1], dtype="datetime64[2s]"), option=16)
    with pytest.raises(TypeError, match="unrepresentable"):
        jsonmodem.dumps(np.datetime64(2**63 - 1, "W"), option=16)
    assert jsonmodem.dumps(np.datetime64(-1, "ns"), option=16) == b'"1969-12-31T23:59:59.999999"'


@pytest.mark.parametrize("data,shape,kind,size,depth", [
    (b"", (1,), "i", 8, 0),
    (b"\0", (1,), "i", 3, 0),
    (b"\0", (1,) * 65, "i", 1, 0),
    (b"\0", (1,), "i", 1, 255),
    (b"", (sys.maxsize, 8), "i", 8, 0),
    (b"\0", (), "unknown", 1, 0),
])
def test_native_metadata_is_checked(data, shape, kind, size, depth):
    with pytest.raises(TypeError):
        native._numpy_dumps(data, shape, kind, size, "", 16, depth)
