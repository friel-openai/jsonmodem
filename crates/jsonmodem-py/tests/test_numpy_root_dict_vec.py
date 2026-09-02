"""Root numeric dictionaries retain key order, callbacks, and snapshots."""

import gc
import types
import weakref

import jsonmodem
import pytest
from jsonmodem import _jsonmodem as native

from test_numpy_root_vec import _NUMERIC_VALUES, _run_child

np = pytest.importorskip("numpy")


@pytest.mark.parametrize("dtype,values", _NUMERIC_VALUES, ids=[x[0] for x in _NUMERIC_VALUES])
@pytest.mark.parametrize("length", [1, 2, 128])
@pytest.mark.parametrize("option", [16, 16 | 1024])
@pytest.mark.parametrize("entry", ["public", "native"])
def test_root_numeric_dict_matches_orjson(dtype, values, length, option, entry):
    orjson = pytest.importorskip("orjson")
    scalar = getattr(np, dtype)
    payload = {
        f"key_{index:03}": scalar(values[index % len(values)])
        for index in range(length)
    }
    if entry == "public":
        result = jsonmodem.dumps(payload, option=option)
    else:
        from jsonmodem import _compat, _numpy

        result = native._dumps_objects(payload, None, option, False, _compat._ENCODER_HELPERS)
    assert result == orjson.dumps(payload, option=option)


@pytest.mark.parametrize("option", [16, 16 | 1024])
def test_root_dict_ascii_escaping_and_insertion_order(option):
    orjson = pytest.importorskip("orjson")
    keys = ["z", "a", "", '"', "\\", "\x00", "\b\f\n\r\t", "\x01\x1f", "\x7f", "x" * 4096]
    keys += ["plain" * 8 + '\x00"\\' * 20, "last"]
    payload = {key: np.uint64(2 ** 64 - 1 - index) for index, key in enumerate(keys)}
    assert jsonmodem.dumps(payload, option=option) == orjson.dumps(payload, option=option)


@pytest.mark.parametrize("codepoint", [0xE9, 0x100, 0x1F600])
@pytest.mark.parametrize("warm_key", [False, True])
def test_root_dict_non_ascii_keys_keep_existing_encoder(codepoint, warm_key):
    orjson = pytest.importorskip("orjson")
    key = "prefix" + chr(codepoint) * 17
    payload = {"first": np.int64(7), key: np.int64(9), "last": np.int64(11)}
    if warm_key:
        assert jsonmodem.dumps(key) == orjson.dumps(key)
    assert jsonmodem.dumps(payload, option=16) == orjson.dumps(payload, option=16)


@pytest.mark.parametrize("option", [16 | 1, 16 | 32, 16 | 64, 16 | 256])
def test_root_dict_other_options_keep_existing_encoder(option):
    orjson = pytest.importorskip("orjson")
    payload = {"z": np.int64(7), "a": np.float32(0.125)}
    assert jsonmodem.dumps(payload, option=option) == orjson.dumps(payload, option=option)


def test_root_dict_non_string_key_conversion_is_unchanged():
    orjson = pytest.importorskip("orjson")
    payload = {7: np.int64(9), None: np.float32(0.125)}
    assert jsonmodem.dumps(payload, option=16 | 4) == orjson.dumps(payload, option=16 | 4)


@pytest.mark.parametrize("kind", ["non_string", "subclass", "surrogate"])
def test_root_dict_late_bad_key_keeps_earlier_default_order(kind):
    class Key(str):
        pass

    key = {"non_string": 1, "subclass": Key("bad"), "surrogate": chr(0xD800)}[kind]
    marker = object()
    calls = []
    payload = {"first": marker, key: np.int64(9)}

    def default(value):
        assert value is marker
        calls.append("default")
        return None

    with pytest.raises(jsonmodem.JSONEncodeError):
        jsonmodem.dumps(payload, option=16, default=default)
    assert calls == ["default"]


def test_root_dict_callback_keeps_owners_after_clear_and_collection(monkeypatch):
    from jsonmodem import _numpy

    calls = []

    class Marker:
        def __del__(self):
            calls.append("finalized")

    marker = Marker()
    owner = weakref.ref(marker)
    payload = {f"key_{index}": np.int64(7) for index in range(128)}
    payload["callback"] = marker
    payload["last"] = np.int64(9)
    del marker

    def replacement(*args):
        calls.append(args[0])
        return b"123"

    def default(value):
        assert type(value) is Marker
        calls.append("default")
        payload.clear()
        gc.collect()
        assert owner() is value and "finalized" not in calls
        monkeypatch.setattr(_numpy.native, "_numpy_dumps", replacement)
        return None

    expected = b"{" + b",".join(
        f'"key_{index}":7'.encode() for index in range(128)
    ) + b',"callback":null,"last":123}'
    assert jsonmodem.dumps(payload, option=16, default=default) == expected
    gc.collect()
    assert payload == {} and owner() is None
    assert calls.count("finalized") == 1
    assert [call for call in calls if call != "finalized"] == ["default", np.int64(9).tobytes()]


@pytest.mark.parametrize("enum_helper", [dict, object])
def test_root_dict_enum_helper_alias_is_not_bypassed(enum_helper, monkeypatch):
    from jsonmodem import _compat, _numpy

    helpers = list(_compat._ENCODER_HELPERS)
    helpers[0] = enum_helper
    helpers = tuple(helpers)
    monkeypatch.setattr(_compat, "_ENCODER_HELPERS", helpers)
    payload = {"first": np.int64(7)}
    with pytest.raises(AttributeError, match="value"):
        jsonmodem.dumps(payload, option=16)
    with pytest.raises(AttributeError, match="value"):
        native._dumps_objects(payload, None, 16, False, helpers)
    with pytest.raises(AttributeError, match="value"):
        native._dumps_objects({}, None, 16, False, helpers)


def test_root_dict_numpy_subclass_keeps_default():
    class CustomInt(np.int64):
        pass

    custom = CustomInt(9)
    calls = []

    def default(value):
        calls.append(value)
        return 123

    payload = {"first": np.int64(7), "custom": custom, "last": np.int64(11)}
    assert jsonmodem.dumps(payload, option=16, default=default) == (
        b'{"first":7,"custom":123,"last":11}'
    )
    assert len(calls) == 1 and calls[0] is custom


@pytest.mark.parametrize("helper", ["native", "native_module", "encode", "special"])
def test_root_dict_current_helper_replacements_are_not_bypassed(helper, monkeypatch):
    from jsonmodem import _compat, _numpy

    payload = {"first": np.int64(7), "second": np.int64(9)}
    calls = []

    def replacement(*args):
        calls.append(args[0])
        return (True, b"123") if helper == "special" else b"123"

    if helper == "special":
        helpers = list(_compat._ENCODER_HELPERS)
        helpers[3] = replacement
        monkeypatch.setattr(_compat, "_ENCODER_HELPERS", tuple(helpers))
    elif helper == "encode":
        monkeypatch.setattr(_numpy, "encode", replacement)
    elif helper == "native_module":
        monkeypatch.setattr(_numpy, "native", types.SimpleNamespace(_numpy_dumps=replacement))
    else:
        monkeypatch.setattr(native, "_numpy_dumps", replacement)
    assert jsonmodem.dumps(payload, option=16) == b'{"first":123,"second":123}'
    if helper in {"native", "native_module"}:
        assert calls == [value.tobytes() for value in payload.values()]
    else:
        assert len(calls) == 2
        assert all(actual is expected for actual, expected in zip(calls, payload.values()))


@pytest.mark.parametrize("name", ["SCALAR_TYPES", "np"])
def test_root_dict_changed_scalar_admission_keeps_default(name, monkeypatch):
    from jsonmodem import _numpy

    payload = {"first": np.int64(7), "second": np.int64(9)}
    calls = []

    def default(value):
        calls.append(value)
        return int(value)

    monkeypatch.setattr(_numpy, name, () if name == "SCALAR_TYPES" else None)
    assert jsonmodem.dumps(payload, option=16, default=default) == b'{"first":7,"second":9}'
    assert len(calls) == 2
    assert all(actual is expected for actual, expected in zip(calls, payload.values()))


@pytest.mark.parametrize("entry", ["public", "native"])
@pytest.mark.parametrize("key_type", ["object", "str"])
def test_root_dict_helper_key_callback_keeps_value_order(entry, key_type, tmp_path):
    import json

    body = r'''
entry, key_type, mode, report_path = sys.argv[1:]
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
payload = {"first": np.int64(7), "second": np.int64(9), "third": np.int64(11)}
raw_values = [np.generic.tobytes(value).hex() for value in payload.values()]

def encode(value):
    if entry == "public":
        return jsonmodem.dumps(value, option=16)
    return native._dumps_objects(value, None, 16, False, _compat._ENCODER_HELPERS)

armed = True
if mode == "scalars":
    result = b"{" + b",".join(
        b'"' + key.encode() + b'":' + encode(value)
        for key, value in payload.items()
    ) + b"}"
elif mode == "container":
    result = encode(payload)
else:
    raise AssertionError("unknown encoding mode")

# The Python fallback observes the replacement before encoding the first value.
native_first = b'{"first":7,"second":123,"third":123}'
fallback_first = b'{"first":123,"second":123,"third":123}'
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
        _run_child(body, entry, key_type, mode, report_path)
        reports.append(json.loads(report_path.read_text()))
    assert reports[0] == reports[1]


@pytest.mark.parametrize("replacement", [False, True])
def test_root_dict_cold_initialization_and_native_replacement(replacement):
    _run_child(r'''
replacement = sys.argv[1] == "True"
payload = {"first": np.int64(7), "second": np.int64(9)}
calls = []
original = native._numpy_dumps
def capture(*args):
    calls.append(args[0])
    return original(*args)
if replacement:
    native._numpy_dumps = capture
assert jsonmodem.dumps(payload, option=16) == b'{"first":7,"second":9}'
assert calls == ([value.tobytes() for value in payload.values()] if replacement else [])
native._numpy_dumps = original
calls.clear()
assert jsonmodem.dumps(payload, option=16) == b'{"first":7,"second":9}'
assert calls == []
''', replacement)


def test_root_dict_surrogate_codec_callback_is_not_preconverted():
    _run_child(r'''
import codecs
import gc

assert jsonmodem.dumps(np.int64(0), option=16) == b"0"
from jsonmodem import _numpy
payload = {"first": np.int64(7), chr(0xD800): np.int64(9), "last": np.int64(11)}
calls = []
strict = codecs.lookup_error("strict")
original = native._numpy_dumps

def replacement(*args):
    calls.append(args[0])
    return b"123"

def replace_key(error):
    assert isinstance(error, UnicodeEncodeError)
    calls.append("strict")
    payload.clear()
    gc.collect()
    native._numpy_dumps = replacement
    return ("replacement", error.end)

try:
    codecs.register_error("strict", replace_key)
    result = jsonmodem.dumps(payload, option=16)
finally:
    codecs.register_error("strict", strict)
    native._numpy_dumps = original
assert result == b'{"first":7,"replacement":123,"last":123}', result
assert calls == ["strict", np.int64(9).tobytes(), np.int64(11).tobytes()], calls
assert payload == {}
''')
