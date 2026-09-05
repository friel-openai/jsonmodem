"""Run invalid-cache regressions only against a build with checked text access."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

import jsonmodem


_CHILD = r'''
import codecs
import ctypes
import dataclasses
import os
from pathlib import Path
import sys

case, package_root, native_path = sys.argv[1:]
sys.path.insert(0, package_root)
import jsonmodem

assert Path(jsonmodem._native.__file__).resolve() == Path(native_path).resolve()
if os.environ.get("JSONMODEM_MEMORY_RUNNER"):
    assert getattr(ctypes.CDLL(None), "__asan_init")
api = ctypes.pythonapi.PyUnicode_AsUTF8AndSize
api.argtypes = [ctypes.py_object, ctypes.POINTER(ctypes.c_ssize_t)]
api.restype = ctypes.c_void_p
text = chr(0xD800)
original = codecs.lookup_error("strict")
assert original is codecs.strict_errors
calls = 0

def replacement(error):
    global calls
    calls += 1
    assert calls == 1 and type(error) is UnicodeEncodeError
    assert error.object is text and error.encoding == "utf-8"
    assert (error.start, error.end) == (0, 1)
    return b"\xff", error.end

try:
    codecs.register_error("strict", replacement)
    size = ctypes.c_ssize_t(-1)
    try:
        pointer = api(text, ctypes.byref(size))
    except UnicodeEncodeError:
        raise SystemExit(77)
    assert pointer is not None and 0 <= size.value <= 16
    copied = ctypes.string_at(pointer, size.value)
finally:
    codecs.register_error("strict", original)
assert codecs.lookup_error("strict") is original
try:
    copied.decode("utf-8", "strict")
except UnicodeDecodeError:
    pass
else:
    raise SystemExit(77)
assert copied == b"\xff" and calls == 1

expected = TypeError
expected_message = None
saved_surrogatepass = codecs.lookup_error("surrogatepass")
if case == "root":
    operation = lambda: jsonmodem.dumps(text)
elif case == "list":
    operation = lambda: jsonmodem.dumps([text])
elif case == "dict_value":
    operation = lambda: jsonmodem.dumps({"key": text})
elif case == "dict_key":
    operation = lambda: jsonmodem.dumps({text: 1})
elif case == "sorted_key":
    operation = lambda: jsonmodem.dumps({text: 1}, option=jsonmodem.OPT_SORT_KEYS)
elif case == "converted_key":
    operation = lambda: jsonmodem.dumps({text: 1}, option=jsonmodem.OPT_NON_STR_KEYS)
elif case == "callback_sorted_key":
    operation = lambda: jsonmodem.dumps(
        object(), default=lambda _: {text: 1}, option=jsonmodem.OPT_SORT_KEYS)
elif case == "callback_converted_key":
    operation = lambda: jsonmodem.dumps(
        object(), default=lambda _: {text: 1}, option=jsonmodem.OPT_NON_STR_KEYS)
elif case == "fragment":
    operation = lambda: jsonmodem.dumps(jsonmodem.Fragment(text))
elif case == "loads":
    operation = lambda: jsonmodem.loads(text)
    expected = jsonmodem.JSONDecodeError
elif case == "dataclass_dict_name":
    @dataclasses.dataclass
    class Record:
        pass
    record = Record()
    record.__dict__ = {text: 1}
    operation = lambda: jsonmodem.dumps(record)
elif case == "dataclass_slot_name":
    @dataclasses.dataclass
    class Record:
        __slots__ = ("value",)
        value: int
    record = Record(1)
    dataclasses.fields(Record)[0].name = text
    operation = lambda: jsonmodem.dumps(record)
elif case in {"events", "tracked_events", "minimal_events", "values"}:
    parser_type = {"events": jsonmodem.JsonModem,
                   "tracked_events": jsonmodem.JsonModemEvents,
                   "minimal_events": jsonmodem.JsonModemEvents,
                   "values": jsonmodem.JsonModemValues}[case]
    if case in {"tracked_events", "minimal_events"}:
        parser = parser_type(track_paths=case == "tracked_events")
    else:
        parser = parser_type()
    operation = lambda: list(parser.feed(text))
    expected = UnicodeError
elif case == "pattern":
    operation = lambda: jsonmodem.JsonModem(paths=text)
    expected = UnicodeError
elif case == "pattern_list":
    operation = lambda: jsonmodem.JsonModem(paths=[text])
elif case == "decode_mode":
    operation = lambda: jsonmodem.DecodeMode(text)
    expected = UnicodeError
elif case == "numpy_kind":
    operation = lambda: jsonmodem._native._numpy_dumps(b"", [0], text, 1, "", 0, 0)
    expected = UnicodeError
elif case == "numpy_unit":
    operation = lambda: jsonmodem._native._numpy_dumps(b"", [0], "u", 1, text, 0, 0)
    expected = UnicodeError
elif case == "payload_key":
    parser = jsonmodem.JsonModem()
    payload = next(payload for kind, _, payload in parser.feed(b'"value"') if kind == "string")
    assert isinstance(payload, jsonmodem.StringPayload)
    operation = lambda: payload[text]
    expected = UnicodeError
elif case in {"keyword_function", "keyword_constructor", "keyword_method"}:
    if case == "keyword_function":
        operation = lambda: jsonmodem.dumps(None, **{text: 0})
        callable_name = "dumps()"
    elif case == "keyword_constructor":
        operation = lambda: jsonmodem.JsonModem(**{text: 0})
        callable_name = "JsonModem.__new__()"
    else:
        parser = jsonmodem.JsonModem()
        operation = lambda: parser.feed(b"[]", **{text: 0})
        callable_name = "JsonModem.feed()"
    expected_message = callable_name + " got an unexpected keyword argument '" + "\ufffd" * 3 + "'"
elif case in {"conversion_error", "conversion_error_handler"}:
    class BadIndex:
        def __index__(self):
            raise TypeError(text)
    if case == "conversion_error_handler":
        def forbidden_handler(error):
            raise AssertionError("error formatting called a replaceable codec handler")
        codecs.register_error("surrogatepass", forbidden_handler)
    operation = lambda: jsonmodem._native._numpy_dumps(b"", [0], "u", BadIndex(), "", 0, 0)
    expected_message = "argument 'itemsize': " + "\ufffd" * 3
elif case in {"path_suffix", "view_key"}:
    parser = jsonmodem.JsonModemValues()
    updates = list(parser.feed(b'{"ok":1}'))
    if case == "path_suffix":
        path = updates[0][2]
        operation = lambda: path.endswith(text)
    else:
        view = parser.view()
        operation = lambda: view[text]
    expected = UnicodeError
else:
    raise AssertionError("unknown case")

try:
    operation()
except expected as error:
    if expected_message is not None:
        assert str(error) == expected_message, repr(error)
    print("rejected invalid cached UTF-8")
else:
    raise AssertionError("invalid cached UTF-8 was accepted")
finally:
    codecs.register_error("surrogatepass", saved_surrogatepass)
assert codecs.lookup_error("strict") is original
assert jsonmodem.dumps({"after": "\u00e9"}) == b'{"after":"\xc3\xa9"}'
'''


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython UTF-8 cache fixture")
@pytest.mark.parametrize(
    "case",
    [
        "root", "list", "dict_value", "dict_key", "sorted_key", "converted_key",
        "callback_sorted_key", "callback_converted_key", "fragment", "loads",
        "dataclass_dict_name", "dataclass_slot_name", "events", "tracked_events", "minimal_events",
        "values", "pattern", "pattern_list", "decode_mode", "payload_key",
        "path_suffix", "view_key", "numpy_kind", "numpy_unit",
        "keyword_function", "keyword_constructor", "keyword_method",
        "conversion_error", "conversion_error_handler",
    ],
)
def test_invalid_utf8_cache_is_rejected_after_handler_restoration(case):
    package_root = Path(jsonmodem.__file__).resolve().parent.parent
    native_path = Path(jsonmodem._native.__file__).resolve()
    runner = os.environ.get("JSONMODEM_MEMORY_RUNNER")
    command = [runner] if runner else []
    result = subprocess.run(
        [*command, sys.executable, "-B", "-c", _CHILD, case, str(package_root), str(native_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode == 77:
        pytest.skip("interpreter does not admit this invalid UTF-8 cache")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "rejected invalid cached UTF-8"


def test_python_repr_results_keep_their_text():
    parser = jsonmodem.JsonModem()
    events = list(parser.feed('{"word":"\u00e9"}'))
    for kind, path, payload in events:
        assert repr(path) == repr(path.as_tuple())
        if kind == "string":
            assert repr(payload) == repr(payload.as_dict())

    parser = jsonmodem.JsonModemValues()
    list(parser.feed('{"word":"\u00e9"}'))
    view = parser.view()
    assert repr(view) == f"JsonModemValueView({view.snapshot()!r})"


def test_checked_string_arguments_keep_valid_values_and_type_errors():
    assert jsonmodem.DecodeMode("StrictUnicode") == jsonmodem.DecodeMode.StrictUnicode
    assert jsonmodem.DecodeMode(None) == jsonmodem.DecodeMode.StrictUnicode
    with pytest.raises(TypeError):
        jsonmodem.DecodeMode(1)

    parser = jsonmodem.JsonModem()
    payload = next(payload for kind, _, payload in parser.feed(b'"value"') if kind == "string")
    assert payload["fragment"] == "value"
    with pytest.raises(TypeError):
        payload[1]

    assert jsonmodem._native._numpy_dumps(b"", [0], "u", 1, "", 0, 0) == b"[]"
    with pytest.raises(TypeError):
        jsonmodem._native._numpy_dumps(b"", [0], 1, 1, "", 0, 0)
    with pytest.raises(TypeError):
        jsonmodem._native._numpy_dumps(b"", [0], "u", 1, 1, 0, 0)


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython codec reentry")
def test_argument_error_formatting_allows_codec_and_finalizer_reentry():
    script = r'''
import codecs
import gc
import sys
sys.path.insert(0, sys.argv[1])
import jsonmodem

calls = []
text = "before\ud800after"

class CodecFailure(Exception):
    def __del__(self):
        assert jsonmodem.dumps({"nested": 2}) == b'{"nested":2}'
        calls.append("finalizer")

def strict(error):
    calls.append("strict")
    assert error.object is text
    assert jsonmodem.dumps({"nested": 1}) == b'{"nested":1}'
    raise CodecFailure()

def surrogatepass(error):
    calls.append("surrogatepass")
    raise AssertionError("lossy formatting invoked a codec handler")

class BadIndex:
    def __index__(self):
        raise TypeError(text)

original_strict = codecs.lookup_error("strict")
original_pass = codecs.lookup_error("surrogatepass")
try:
    codecs.register_error("strict", strict)
    codecs.register_error("surrogatepass", surrogatepass)
    try:
        jsonmodem._native._numpy_dumps(b"", [0], "u", BadIndex(), "", 0, 0)
    except TypeError as error:
        assert str(error) == "argument 'itemsize': before" + "\ufffd" * 3 + "after"
    else:
        raise AssertionError("invalid item size was accepted")
    gc.collect()
finally:
    codecs.register_error("strict", original_strict)
    codecs.register_error("surrogatepass", original_pass)
assert calls == ["strict", "finalizer"], calls
assert jsonmodem.dumps([1, 2, 3]) == b"[1,2,3]"
print("codec and finalizer reentry passed")
'''
    package_root = Path(jsonmodem.__file__).resolve().parent.parent
    runner = os.environ.get("JSONMODEM_MEMORY_RUNNER")
    command = [runner] if runner else []
    result = subprocess.run(
        [*command, sys.executable, "-B", "-c", script, str(package_root)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "codec and finalizer reentry passed"
