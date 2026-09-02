"""Root numeric sequences preserve helper callbacks and complete snapshots."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import jsonmodem
import pytest
from jsonmodem import _jsonmodem as native

np = pytest.importorskip("numpy")


_CHILD_SETUP = r'''
import hashlib
import json
import os
from pathlib import Path
import sys

import jsonmodem
import numpy as np
from jsonmodem import _jsonmodem as native

if os.environ.get("JSONMODEM_MEMORY_RUNNER"):
    import ctypes
    assert getattr(ctypes.CDLL(None), "__asan_init")
assert "jsonmodem._numpy" not in sys.modules
'''

_CHILD_IDENTITY = r'''
from jsonmodem import _numpy
print(json.dumps({
    "pid": os.getpid(),
    "python": str(Path(sys.executable).resolve()),
    "package": str(Path(jsonmodem.__file__).resolve()),
    "native": str(Path(native.__file__).resolve()),
    "native_sha256": hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
    "helper": str(Path(_numpy.__file__).resolve()),
    "helper_sha256": hashlib.sha256(Path(_numpy.__file__).read_bytes()).hexdigest(),
}), flush=True)
'''


def _run_child(body, *arguments):
    # General-key module dictionaries cannot regain Unicode storage by deleting
    # just the custom key. Keep those mutations in a separate process.
    runner = os.environ.get("JSONMODEM_MEMORY_RUNNER")
    command = [runner] if runner else []
    process = subprocess.run(
        [*command, sys.executable, "-B", "-c",
         _CHILD_SETUP + body + _CHILD_IDENTITY, *map(str, arguments)],
        capture_output=True, text=True, timeout=30,
    )
    print(process.stdout, end="")
    assert process.returncode == 0, process.stdout + process.stderr
    identity = json.loads(process.stdout)
    assert identity["python"] == str(Path(sys.executable).resolve())
    assert identity["package"] == str(Path(jsonmodem.__file__).resolve())
    assert identity["native"] == str(Path(native.__file__).resolve())
    assert identity["native_sha256"] == hashlib.sha256(
        Path(native.__file__).read_bytes()
    ).hexdigest()
    helper = Path(jsonmodem.__file__).resolve().with_name("_numpy.py")
    assert identity["helper"] == str(helper)
    assert identity["helper_sha256"] == hashlib.sha256(helper.read_bytes()).hexdigest()


@pytest.mark.parametrize("key_type", ["object", "str"])
@pytest.mark.parametrize("length", [2, 1024])
@pytest.mark.parametrize("container", ["list", "tuple"])
@pytest.mark.parametrize("entry", ["public", "native"])
def test_root_helper_key_callback_keeps_original_order(key_type, length, container, entry, tmp_path):
    body = r'''
key_type, length, container, entry, mode, report_path = sys.argv[1:]
length = int(length)
assert jsonmodem.dumps(np.int64(0), option=16) == b"0"
from jsonmodem import _compat, _numpy
scalar_types = _numpy.SCALAR_TYPES
armed = False
calls = []
events = []

def replacement(*args):
    calls.append(args[0])
    events.append(["encode", args[0].hex()])
    return b"123"

def matches(other):
    global armed
    events.append(["lookup", other])
    if other != "SCALAR_TYPES":
        return False
    if armed:
        armed = False
        native._numpy_dumps = replacement
    return True

class GuardKey:
    def __hash__(self):
        return hash("SCALAR_TYPES")
    def __eq__(self, other):
        return matches(other)

class GuardStr(str):
    __hash__ = str.__hash__
    def __eq__(self, other):
        return matches(other)

key = GuardKey() if key_type == "object" else GuardStr("SCALAR_TYPES")
del _numpy.__dict__["SCALAR_TYPES"]
_numpy.__dict__[key] = scalar_types
first, later = np.int64(7), np.int64(9)
payload = [first] + [later] * (length - 1)
if container == "tuple":
    payload = tuple(payload)
raw_values = [np.generic.tobytes(value).hex() for value in payload]

def encode(value):
    if entry == "public":
        return jsonmodem.dumps(value, option=16)
    return native._dumps_objects(value, None, 16, False, _compat._ENCODER_HELPERS)

armed = True
if mode == "scalars":
    result = b"[" + b",".join(encode(value) for value in payload) + b"]"
elif mode == "container":
    result = encode(payload)
else:
    raise AssertionError("unknown encoding mode")

# The Python fallback observes the replacement before encoding the first value.
native_first = b"[7" + b",123" * (length - 1) + b"]"
fallback_first = b"[" + b",".join([b"123"] * length) + b"]"
assert result in (native_first, fallback_first), result
first_is_native = result == native_first
expected_calls = raw_values[1:] if first_is_native else raw_values
call_bytes = [value.hex() for value in calls]
assert call_bytes == expected_calls, calls
expected_events = []
for index, raw in enumerate(raw_values):
    expected_events.append(["lookup", "SCALAR_TYPES"])
    if index or not first_is_native:
        expected_events.append(["encode", raw])
assert events == expected_events, events
assert not armed
with Path(report_path).open("x") as report:
    json.dump({"result": result.hex(), "calls": call_bytes, "events": events}, report)
'''
    # Fresh children give both encoders the same unmodified helper dictionaries.
    reports = []
    for mode in ("scalars", "container"):
        report_path = tmp_path / f"{mode}.json"
        _run_child(body, key_type, length, container, entry, mode, report_path)
        reports.append(json.loads(report_path.read_text()))
    assert reports[0] == reports[1]


@pytest.mark.parametrize("dictionary", ["modules", "module", "native"])
@pytest.mark.parametrize("key_type", ["object", "str"])
def test_root_attempt_does_not_add_helper_key_comparisons(dictionary, key_type):
    _run_child(r'''
dictionary, key_type = sys.argv[1:]
assert jsonmodem.dumps(np.int64(0), option=16) == b"0"
from jsonmodem import _numpy
if dictionary == "modules":
    mapping, name = sys.modules, "jsonmodem._numpy"
elif dictionary == "module":
    mapping, name = _numpy.__dict__, "SCALAR_TYPES"
else:
    mapping, name = native.__dict__, "_numpy_dumps"
original = mapping[name]
calls = []

class GuardKey:
    def __hash__(self):
        return hash(name)
    def __eq__(self, other):
        calls.append(other)
        return other == name

class GuardStr(str):
    __hash__ = str.__hash__
    def __eq__(self, other):
        calls.append(other)
        return str.__eq__(self, other)

key = GuardKey() if key_type == "object" else GuardStr(name)
del mapping[name]
mapping[key] = original
calls.clear()
assert jsonmodem.dumps([np.int64(7), np.int64(9)], option=16) == b"[7,9]"
assert calls == [name, name], calls
''', dictionary, key_type)


_NUMERIC_VALUES = [
    ("bool_", [False, True]),
    ("int8", [-128, -1, 0, 127]),
    ("int16", [-32768, -1, 0, 32767]),
    ("int32", [-(2 ** 31), -1, 0, 2 ** 31 - 1]),
    ("int64", [-(2 ** 63), -1, 0, 2 ** 63 - 1]),
    ("uint8", [0, 255]),
    ("uint16", [0, 65535]),
    ("uint32", [0, 2 ** 32 - 1]),
    ("uint64", [0, 2 ** 64 - 1]),
    ("float16", [-0.0, 0.12345, 65504, float("inf"), float("nan")]),
    ("float32", [-0.0, 0.12345, 1e-20, float("-inf"), float("nan")]),
    ("float64", [-0.0, 0.12345, 1e-100, float("inf"), float("nan")]),
]


@pytest.mark.parametrize("dtype,values", _NUMERIC_VALUES, ids=[x[0] for x in _NUMERIC_VALUES])
@pytest.mark.parametrize("container", [list, tuple])
@pytest.mark.parametrize("length", [1, 2, 1024])
@pytest.mark.parametrize("option", [16, 16 | 1024])
def test_root_numeric_sequence_matches_orjson(dtype, values, container, length, option):
    orjson = pytest.importorskip("orjson")
    scalar = getattr(np, dtype)
    payload = container(scalar(values[index % len(values)]) for index in range(length))
    assert jsonmodem.dumps(payload, option=option) == orjson.dumps(payload, option=option)


@pytest.mark.parametrize("container", [list, tuple])
@pytest.mark.parametrize("option", [17, 16 | 64, 16 | 256])
def test_root_other_options_keep_existing_encoding(container, option):
    orjson = pytest.importorskip("orjson")
    payload = container([np.int64(7), np.uint64(2 ** 64 - 1), np.float32(0.125)])
    assert jsonmodem.dumps(payload, option=option) == orjson.dumps(payload, option=option)


@pytest.mark.parametrize("container", [list, tuple])
def test_root_mixed_sequence_keeps_snapshot_and_helper_replacement(container, monkeypatch):
    from jsonmodem import _numpy

    marker = object()
    first, last = np.int64(7), np.int64(9)
    source = [first] * 1024 + [marker, last]
    payload = source if container is list else tuple(source)
    calls = []

    def replacement(*args):
        calls.append(args[0])
        return b"123"

    def default(value):
        assert value is marker
        calls.append("default")
        source.clear()
        monkeypatch.setattr(_numpy.native, "_numpy_dumps", replacement)
        return None

    expected = b"[" + b",".join([b"7"] * 1024) + b",null,123]"
    assert jsonmodem.dumps(payload, option=16, default=default) == expected
    assert calls == ["default", np.generic.tobytes(last)]
    assert source == []


@pytest.mark.parametrize("container", [list, tuple])
def test_root_numpy_subclass_is_not_admitted(container):
    class CustomInt(np.int64):
        pass

    custom = CustomInt(9)
    payload = container([np.int64(7), custom, np.int64(11)])
    calls = []

    def default(value):
        calls.append(value)
        return 123

    assert jsonmodem.dumps(payload, option=16, default=default) == b"[7,123,11]"
    assert len(calls) == 1 and calls[0] is custom


@pytest.mark.parametrize("container", ["list", "tuple"])
@pytest.mark.parametrize("replacement", [False, True])
def test_root_cold_initialization_and_native_replacement(container, replacement):
    _run_child(r'''
container, replacement = sys.argv[1:]
replacement = replacement == "True"
payload = [np.int64(7), np.int64(9)]
if container == "tuple":
    payload = tuple(payload)
calls = []
original = native._numpy_dumps
def capture(*args):
    calls.append(args[0])
    return original(*args)
if replacement:
    native._numpy_dumps = capture
assert jsonmodem.dumps(payload, option=16) == b"[7,9]"
assert calls == ([np.generic.tobytes(value) for value in payload] if replacement else [])
native._numpy_dumps = original
calls.clear()
assert jsonmodem.dumps(payload, option=16) == b"[7,9]"
assert calls == []
''', container, replacement)


@pytest.mark.parametrize("container", [list, tuple])
@pytest.mark.parametrize("enum_helper", ["root", "object"])
def test_root_enum_helper_alias_is_not_bypassed(container, enum_helper, monkeypatch):
    from jsonmodem import _compat, _numpy

    helpers = list(_compat._ENCODER_HELPERS)
    helpers[0] = container if enum_helper == "root" else object
    monkeypatch.setattr(_compat, "_ENCODER_HELPERS", tuple(helpers))
    payload = container([np.int64(7), np.int64(9)])
    with pytest.raises(AttributeError, match="value"):
        jsonmodem.dumps(payload, option=16)
    with pytest.raises(AttributeError, match="value"):
        native._dumps_objects(payload, None, 16, False, tuple(helpers))
    assert native._dumps_objects(container(), None, 16, False, tuple(helpers)) == b"[]"


@pytest.mark.parametrize("length", [0, 3, 11])
def test_root_native_entry_preserves_short_helper_errors(length):
    from jsonmodem import _compat, _numpy

    with pytest.raises(IndexError):
        native._dumps_objects([np.int64(7)], None, 16, False, _compat._ENCODER_HELPERS[:length])
