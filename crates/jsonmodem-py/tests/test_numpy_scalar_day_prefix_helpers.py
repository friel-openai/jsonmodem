"""Mixed NumPy values must observe helper changes and retain owning snapshots."""

import json
import types

import jsonmodem
import pytest

np = pytest.importorskip("numpy")

LEFT_TEXT = (
    "2000-02-28T01:02:03.123456",
    "2000-02-28T04:05:06.000001",
    "2000-02-29T00:00:00",
)
RIGHT_TEXT = (
    "2024-03-01T12:30:00.654321",
    "2024-03-01T00:00:00",
    "2024-03-02T08:09:10.000001",
)
FRESH_TEXT = (
    "2031-07-04T01:02:03.000004",
    "2031-07-04T00:00:00",
    "2031-07-05T12:34:56.654321",
)


def expected_bytes(value, option):
    kwargs = {"indent": 2} if option & 1 else {"separators": (",", ":")}
    encoded = json.dumps(value, **kwargs).encode("ascii")
    return encoded + b"\n" if option & 1024 else encoded


@pytest.mark.parametrize("helper", ("native", "encode", "native_module"))
@pytest.mark.parametrize("option", (16, 17, 16 | 1024, 17 | 1024))
def test_mixed_dates_and_scalar_observe_helper_replacement_and_restoration(
    helper, option, monkeypatch
):
    from jsonmodem import _compat, _numpy

    original_native = _numpy.native
    original_dumps = original_native._numpy_dumps
    original_encode = _numpy.encode
    assert _numpy._NATIVE_NUMERIC_TYPES is not None
    assert _compat._ENCODER_HELPERS[12] is _numpy._NATIVE_NUMERIC_TYPES
    assert jsonmodem.dumps(np.int64(0), option=16) == b"0"

    left = np.array(LEFT_TEXT, dtype="datetime64[us]")
    right = np.array(RIGHT_TEXT, dtype="datetime64[us]")
    fresh = np.array(FRESH_TEXT, dtype="datetime64[us]")
    scalar = np.int64(7)
    scalar_snapshot = memoryview(scalar).tobytes()
    right_snapshot = right.tobytes()
    marker = object()
    calls = []
    defaults = []

    def capture(*args):
        calls.append(args)
        if helper == "encode":
            result = original_encode(*args)
            if args[0] is right:
                right[:] = fresh
            return result
        if args[2] == "M":
            # The native helper has already received its owning bytes snapshot.
            right[:] = fresh
        return original_dumps(*args)

    with monkeypatch.context() as changes:
        def default(value):
            assert value is marker
            defaults.append(value)
            if helper == "encode":
                changes.setattr(_numpy, "encode", capture)
            elif helper == "native_module":
                changes.setattr(_numpy, "native", types.SimpleNamespace(_numpy_dumps=capture))
            else:
                changes.setattr(original_native, "_numpy_dumps", capture)
            return None

        output = jsonmodem.dumps([left, marker, scalar, right], option=option, default=default)
        assert output == expected_bytes([list(LEFT_TEXT), None, 7, list(RIGHT_TEXT)], option)
        assert defaults == [marker]
        assert len(calls) == 2
        if helper == "encode":
            assert calls[0][0] is scalar
            assert calls[1][0] is right
        else:
            assert type(calls[0][0]) is bytes
            assert type(calls[1][0]) is bytes
            assert calls[0][0] == scalar_snapshot
            assert calls[0][1:5] == ((), "i", 8, "")
            assert calls[1][0] == right_snapshot
            assert calls[1][1:5] == ((3,), "M", 8, "us")
        assert right.tobytes() == fresh.tobytes()

    assert _numpy.native is original_native
    assert original_native._numpy_dumps is original_dumps
    assert _numpy.encode is original_encode
    recovered = jsonmodem.dumps([np.int64(9), right], option=option)
    assert recovered == expected_bytes([9, list(FRESH_TEXT)], option)
    assert len(calls) == 2
