"""Per-value checks observe helper changes without borrowing mutable storage."""

import os
import subprocess
import sys
import types

import jsonmodem
import pytest
from jsonmodem import _jsonmodem as native

np = pytest.importorskip("numpy")
orjson = pytest.importorskip("orjson")


def test_native_replacement_before_first_numpy_call():
    code = """
import os
import sys
import jsonmodem
import numpy as np
from jsonmodem import _jsonmodem as native
if os.environ.get('JSONMODEM_MEMORY_RUNNER'):
    import ctypes
    assert getattr(ctypes.CDLL(None), '__asan_init')
assert 'jsonmodem._numpy' not in sys.modules
original = native._numpy_dumps
calls = []
def capture(*args):
    calls.append(args)
    return original(*args)
native._numpy_dumps = capture
assert jsonmodem.dumps(np.int64(7), option=16) == b'7'
assert jsonmodem.dumps(np.int64(9), option=16) == b'9'
assert len(calls) == 2
assert all(type(args[0]) is bytes for args in calls)
native._numpy_dumps = original
assert jsonmodem.dumps(np.int64(11), option=16) == b'11'
assert len(calls) == 2
"""
    runner = os.environ.get("JSONMODEM_MEMORY_RUNNER")
    command = [runner] if runner else []
    process = subprocess.run([*command, sys.executable, "-B", "-c", code],
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stdout + process.stderr


@pytest.mark.parametrize("helper", ["native", "encode", "native_module"])
@pytest.mark.parametrize("option", [16, 17, 16 | 1024, 17 | 1024])
def test_default_callback_replaces_helper_before_later_scalar(helper, option, monkeypatch):
    from jsonmodem import _numpy

    first, last = np.int64(7), np.float32(0.12345)
    marker = object()
    calls = []
    original = _numpy.encode if helper == "encode" else native._numpy_dumps

    def capture(*args):
        calls.append(args)
        return original(*args)

    def default(value):
        assert value is marker
        if helper == "encode":
            monkeypatch.setattr(_numpy, "encode", capture)
        elif helper == "native_module":
            monkeypatch.setattr(_numpy, "native", types.SimpleNamespace(_numpy_dumps=capture))
        else:
            monkeypatch.setattr(native, "_numpy_dumps", capture)
        return None

    expected = orjson.dumps([first, None, last], option=option)
    assert jsonmodem.dumps([first, marker, last], option=option, default=default) == expected
    assert len(calls) == 1
    if helper == "encode":
        assert calls[0][0] is last
    else:
        assert type(calls[0][0]) is bytes
        assert calls[0][0] == np.generic.tobytes(last)


def test_default_callback_restores_native_helper(monkeypatch):
    from jsonmodem import _numpy

    first, last = np.int64(7), np.int64(9)
    marker = object()
    original = native._numpy_dumps
    captured = []

    def capture(*args):
        captured.append(args[0])
        return original(*args)

    def default(value):
        assert value is marker
        monkeypatch.setattr(native, "_numpy_dumps", original)
        return None

    monkeypatch.setattr(_numpy.native, "_numpy_dumps", capture)
    assert jsonmodem.dumps([first, marker, last], option=16, default=default) == b"[7,null,9]"
    assert captured == [np.generic.tobytes(first)]


@pytest.mark.parametrize("replacement", ["SCALAR_TYPES", "np"])
def test_default_callback_changes_scalar_admission(replacement, monkeypatch):
    from jsonmodem import _numpy

    first, last = np.int64(7), np.int64(9)
    marker = object()
    calls = []

    def default(value):
        calls.append(value)
        if value is marker:
            monkeypatch.setattr(_numpy, replacement, () if replacement == "SCALAR_TYPES" else None)
            return None
        assert value is last
        return int(value)

    assert jsonmodem.dumps([first, marker, last], option=16, default=default) == b"[7,null,9]"
    assert len(calls) == 2 and calls[0] is marker and calls[1] is last


@pytest.mark.parametrize("during_callback", [False, True])
def test_replaced_numpy_module_is_used(during_callback, monkeypatch):
    from jsonmodem import _numpy

    first, last = np.int64(7), np.int64(9)
    marker = object()
    calls = []
    replacement = types.ModuleType("jsonmodem._numpy")

    def encode(value, option, default_provided, depth):
        calls.append(value)
        return b"123"

    replacement.encode = encode

    def default(value):
        assert value is marker
        monkeypatch.setitem(sys.modules, "jsonmodem._numpy", replacement)
        return None

    if during_callback:
        assert jsonmodem.dumps([first, marker, last], option=16, default=default) == b"[7,null,123]"
    else:
        monkeypatch.setitem(sys.modules, "jsonmodem._numpy", replacement)
        assert jsonmodem.dumps(last, option=16) == b"123"
    assert len(calls) == 1 and calls[0] is last


def test_helper_tuple_replacement_waits_for_next_encode(monkeypatch):
    from jsonmodem import _compat, _numpy

    value = np.int64(9)
    marker = object()
    calls = []

    def special(obj, option, default_provided, depth):
        calls.append(obj)
        return True, b"123"

    def default(obj):
        assert obj is marker
        helpers = list(_compat._ENCODER_HELPERS)
        helpers[3] = special
        monkeypatch.setattr(_compat, "_ENCODER_HELPERS", tuple(helpers))
        return None

    # ObjectEncoder owns the tuple it received, including the original special.
    assert jsonmodem.dumps([marker, value], option=16, default=default) == b"[null,9]"
    assert calls == []
    assert jsonmodem.dumps(value, option=16) == b"123"
    assert len(calls) == 1 and calls[0] is value
