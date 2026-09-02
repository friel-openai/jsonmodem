"""Direct numeric output preserves values, options, and subclass fallback."""

import random
import struct
import sys
import warnings
import weakref

import jsonmodem
import pytest
from jsonmodem import _jsonmodem as native

np = pytest.importorskip("numpy")
orjson = pytest.importorskip("orjson")

NAMES = (
    "bool_", "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32",
    "uint64", "float16", "float32", "float64",
)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("option", [16, 17, 16 | 64, 16 | 1024, 17 | 1024])
def test_numeric_scalar_and_containers_match_reference(name, option):
    value = getattr(np, name)(7)
    for obj in (value, [value, value], {"a": value, "b": [value]}):
        assert jsonmodem.dumps(obj, option=option) == orjson.dumps(obj, option=option)


@pytest.mark.parametrize("name", NAMES)
def test_numeric_helper_replacements_remain_visible(name, monkeypatch):
    from jsonmodem import _compat, _numpy

    value = getattr(np, name)(7)
    expected = orjson.dumps(value, option=16)
    for helper in ("native", "encode", "special"):
        calls = []
        target = {
            "native": native._numpy_dumps,
            "encode": _numpy.encode,
            "special": _compat._ENCODER_HELPERS[3],
        }[helper]

        def capture(*args):
            calls.append(args)
            return target(*args)

        with monkeypatch.context() as patch:
            if helper == "special":
                helpers = list(_compat._ENCODER_HELPERS)
                helpers[3] = capture
                patch.setattr(_compat, "_ENCODER_HELPERS", tuple(helpers))
            else:
                patch.setattr(native if helper == "native" else _numpy,
                              "_numpy_dumps" if helper == "native" else "encode", capture)
            assert jsonmodem.dumps(value, option=16) == expected
            assert len(calls) == 1, helper
            if helper == "native":
                assert type(calls[0][0]) is bytes
                assert calls[0][0] == np.generic.tobytes(value)
            else:
                assert calls[0][0] is value
        assert jsonmodem.dumps(value, option=16) == expected


@pytest.mark.parametrize("name", NAMES[1:9])
def test_integer_limits_ignore_python_integer_strict_option(name):
    kind = getattr(np, name)
    limits = np.iinfo(kind)
    for value in (kind(limits.min), kind(limits.max)):
        for option in (16, 16 | 64, 16 | 64 | 1024):
            assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)


def test_every_float16_pattern_matches_reference():
    for value in np.arange(65536, dtype=np.uint16).view(np.float16):
        assert jsonmodem.dumps(value, option=16) == orjson.dumps(value, option=16)


@pytest.mark.parametrize("width, dtype", [(4, np.float32), (8, np.float64)])
def test_float_bit_samples_match_reference(width, dtype):
    rng = random.Random(1729)
    raw = b"".join(rng.getrandbits(width * 8).to_bytes(width, "little") for _ in range(4096))
    for value in np.frombuffer(raw, dtype=dtype):
        assert jsonmodem.dumps(value, option=16) == orjson.dumps(value, option=16)
    for value in map(dtype, (-0.0, 0.0, float("inf"), -float("inf"), float("nan"))):
        assert jsonmodem.dumps(value, option=16) == orjson.dumps(value, option=16)


@pytest.mark.parametrize("levels", [253, 254, 255, 256])
def test_nested_numpy_scalar_depth(levels):
    value = np.int64(7)
    for _ in range(levels):
        value = [value]
    if levels <= 254:
        assert jsonmodem.dumps(value, option=16) == orjson.dumps(value, option=16)
    else:
        with pytest.raises(TypeError):
            jsonmodem.dumps(value, option=16)


def test_default_can_return_numeric_scalar():
    value = object()
    default = lambda obj: np.float32(0.12345)
    assert jsonmodem.dumps([value], option=16, default=default) == orjson.dumps(
        [value], option=16, default=default)


class ScalarEquality(type):
    __hash__ = type.__hash__

    def __eq__(cls, other):
        return other is np.int64


def test_custom_metaclass_keeps_forced_numpy_base_copy():
    class Scalar(np.int64, metaclass=ScalarEquality):
        def __buffer__(self, flags):
            return memoryview(struct.pack("=q", 999))

    assert jsonmodem.dumps(Scalar(7), option=16) == b"7"


def test_subclass_is_not_a_native_buffer_source():
    class Scalar(np.int64):
        def __buffer__(self, flags):
            raise AssertionError("subclass buffer entered numeric discovery")

    value = Scalar(7)
    with pytest.raises(TypeError):
        jsonmodem.dumps(value, option=16)
    assert jsonmodem.dumps(value, option=16, default=int) == b"7"


def test_type_initialization_never_calls_dtype_factory(monkeypatch):
    from jsonmodem import _compat, _numpy

    def forbidden(*args):
        raise AssertionError("numeric table used replaceable dtype factory")

    monkeypatch.setattr(np, "dtype", forbidden)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        table = native._NumericScalarTypes(np, _numpy.SCALAR_TYPES)
    monkeypatch.setattr(_numpy, "_NATIVE_NUMERIC_TYPES", table)
    monkeypatch.setattr(_compat, "_ENCODER_HELPERS", _compat._ENCODER_HELPERS[:12] + (table,))
    assert jsonmodem.dumps(np.int64(7), option=16) == b"7"


def test_reentrant_initialization_keeps_old_helpers_owned(monkeypatch):
    import gc
    from jsonmodem import _compat

    class KeyText:
        def __call__(self, value, option):
            return str(value)

    original_helpers = _compat._ENCODER_HELPERS
    original_constructor = native._NumericScalarTypes
    marker = KeyText()
    reference = weakref.ref(marker)
    helpers = list(original_helpers[:12])
    helpers[2] = marker
    monkeypatch.setattr(_compat, "_ENCODER_HELPERS", tuple(helpers) + (None,))
    del helpers, marker
    monkeypatch.delitem(sys.modules, "jsonmodem._numpy", raising=False)
    monkeypatch.delattr(jsonmodem, "_numpy", raising=False)
    seen = []

    def initialize(*args):
        # A second monkeypatch.setattr would retain the old tuple in its undo
        # list and conceal an ObjectEncoder ownership mistake.
        _compat._ENCODER_HELPERS = original_helpers[:12] + (None,)
        gc.collect()
        seen.append(reference() is not None)
        assert jsonmodem.dumps(object(), default=lambda value: {"nested": 7}) == b'{"nested":7}'
        seen.append(reference() is not None)
        return original_constructor(*args)

    monkeypatch.setattr(native, "_NumericScalarTypes", initialize)
    assert jsonmodem.dumps(np.int64(7), option=16) == b"7"
    assert seen == [True, True]
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("value", [np.arange(16, dtype=np.int64), np.datetime64("2000-01-01", "us")])
def test_arrays_and_dates_still_use_snapshot_helper(value, monkeypatch):
    seen = []
    original = native._numpy_dumps

    def capture(*args):
        seen.append(args[0])
        return original(*args)

    monkeypatch.setattr(native, "_numpy_dumps", capture)
    assert jsonmodem.dumps(value, option=16) == orjson.dumps(value, option=16)
    assert len(seen) == 1 and type(seen[0]) is bytes
