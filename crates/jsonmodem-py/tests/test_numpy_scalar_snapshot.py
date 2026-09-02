"""Scalar snapshots retain base-method and helper replacement behavior."""

import struct

import jsonmodem
import pytest

np = pytest.importorskip("numpy")


@pytest.mark.parametrize("dtype", (
    "bool", "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32",
    "uint64", "float16", "float32", "float64", "datetime64[us]", "datetime64[ns]",
))
def test_scalar_snapshot_is_immutable_and_matches_base_method(dtype, monkeypatch):
    from jsonmodem import _jsonmodem as native

    value = np.array(7, dtype=dtype)[()]
    expected = np.generic.tobytes(value)
    captured = []
    original = native._numpy_dumps

    def capture(data, *args):
        assert type(data) is bytes
        captured.append(data)
        return original(data, *args)

    monkeypatch.setattr(native, "_numpy_dumps", capture)
    result = jsonmodem.dumps(value, option=16)
    assert captured == [expected]
    assert result == jsonmodem.dumps(value, option=16)
    assert captured == [expected, expected]


def test_ordinary_scalar_subclass_keeps_default_handling():
    class Scalar(np.int64):
        def __buffer__(self, flags):
            raise AssertionError("subclass buffer must not be used")

    value = Scalar(7)
    with pytest.raises(TypeError):
        jsonmodem.dumps(value, option=16)
    assert jsonmodem.dumps(value, option=16, default=lambda obj: int(obj)) == b"7"


class ScalarEquality(type):
    __hash__ = type.__hash__

    def __eq__(cls, other):
        return other is np.int64


def test_custom_metaclass_cannot_admit_a_buffer_as_numpy():
    class NotScalar(metaclass=ScalarEquality):
        dtype = np.dtype("int64")

        def __buffer__(self, flags):
            raise AssertionError("non-scalar buffer must not be used")

    with pytest.raises(TypeError):
        jsonmodem.dumps(NotScalar(), option=16)


def test_custom_metaclass_scalar_keeps_base_method_copy():
    class Scalar(np.int64, metaclass=ScalarEquality):
        def __buffer__(self, flags):
            return memoryview(struct.pack("=q", 999))

    assert jsonmodem.dumps(Scalar(7), option=16) == b"7"
