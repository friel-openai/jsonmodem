"""Fixed numeric metadata preserves scalar admission and helper arguments."""

import jsonmodem
import pytest

np = pytest.importorskip("numpy")


@pytest.mark.parametrize("name", (
    "bool_", "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32",
    "uint64", "float16", "float32", "float64",
))
@pytest.mark.parametrize("number", (0, 1, 7))
def test_numeric_scalar_helper_metadata(name, number, monkeypatch):
    from jsonmodem import _numpy

    value = getattr(np, name)(number)
    calls = []

    def capture(*args):
        calls.append(args)
        return b"replacement"

    monkeypatch.setattr(_numpy.native, "_numpy_dumps", capture)
    assert _numpy.encode(value, 16, False, depth=9) == b"replacement"
    assert calls == [(
        np.generic.tobytes(value), (), value.dtype.kind, value.dtype.itemsize,
        "", 16, 9,
    )]
    assert type(calls[0][0]) is bytes


def test_scalar_admission_still_uses_current_tuple(monkeypatch):
    from jsonmodem import _numpy

    monkeypatch.setattr(_numpy, "SCALAR_TYPES", ())
    assert _numpy.encode(np.int64(7), 16, False) is None


@pytest.mark.parametrize("unit", ("Y", "M", "D", "h", "m", "s", "ms", "us", "ns"))
def test_datetime_metadata_remains_per_value(unit, monkeypatch):
    from jsonmodem import _numpy

    value = np.datetime64(7, unit)
    calls = []

    def capture(*args):
        calls.append(args)
        return b"replacement"

    monkeypatch.setattr(_numpy.native, "_numpy_dumps", capture)
    assert _numpy.encode(value, 16, False, depth=9) == b"replacement"
    assert calls == [(np.generic.tobytes(value), (), "M", 8, unit, 16, 9)]
