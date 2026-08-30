"""Early errors keep precedence when a root container has an invalid ending."""

from array import array
import json
import math

import jsonmodem
import pytest


INPUT_KINDS = ("str", "bytes", "bytearray", "memoryview", "array_view")


def as_input(text, kind):
    if kind == "str":
        return text
    raw = text.encode()
    if kind == "array_view":
        return memoryview(array("B", raw))
    return {"bytes": bytes, "bytearray": bytearray, "memoryview": memoryview}[kind](raw)


def assert_first_error_is_unchanged(text, kind):
    prefix = " " * 128
    with pytest.raises(jsonmodem.JSONDecodeError) as direct:
        jsonmodem.loads(as_input(text, kind))
    with pytest.raises(jsonmodem.JSONDecodeError) as prefixed:
        jsonmodem.loads(as_input(prefix + text, kind))
    first = direct.value
    second = prefixed.value
    assert first.msg == second.msg
    assert first.pos + len(prefix) == second.pos
    assert first.lineno == second.lineno
    assert first.colno + (len(prefix) if first.lineno == 1 else 0) == second.colno
    assert first.doc == text
    assert second.doc == prefix + text


@pytest.mark.parametrize("kind", INPUT_KINDS)
@pytest.mark.parametrize("root", ["array", "object"])
@pytest.mark.parametrize("tail", [
    "0}", "0] 0", "0],", "0] true", "0] false", "0] null",
    "!}", ",}", ":}", "01}", "-}", "1.}", "1e+}", "1e400}",
    "-1e400}", "99999999999999999999999999999999999999999999999999e400}",
    '"\\q"}', '"\\uD800"}', '"\\uDC00"}', '"\\uD800\\u1234"}',
    '"\\u12"}', '"unfinished}', '"unfinished\\}',
    '"line\nfeed"}', '"\u00e9\u2603\U0001f600"}',
    '{"a":0,}', '{"a" 0}', '{"a":0 "b":1}', '[0,}', '[0 1}',
    'true false}', 'nul}', 'falsex}', '[]}', '{}] 0',
])
def test_invalid_container_ending_preserves_first_error(kind, root, tail):
    padding = "p" * 1100
    if root == "array":
        text = '["' + padding + '",' + tail
    else:
        text = '{"padding":"' + padding + '","value":' + tail.replace("}", "]")
    assert_first_error_is_unchanged(text, kind)


@pytest.mark.parametrize("kind", INPUT_KINDS)
@pytest.mark.parametrize("leading", ["", " ", " \n\t", " " * 63, " " * 64])
@pytest.mark.parametrize("trailing", ["", " ", "\r\n\t", " " * 63, " " * 64])
@pytest.mark.parametrize("length", [0, 900, 1024, 4096])
def test_whitespace_and_size_do_not_change_error_precedence(kind, leading, trailing, length):
    text = leading + '["' + "\u00e9" * length + '",1e400}' + trailing
    assert_first_error_is_unchanged(text, kind)


@pytest.mark.parametrize("kind", INPUT_KINDS)
@pytest.mark.parametrize("ending", ["}", "] 0", "]\v", "]\f", "]\u00a0"])
def test_invalid_endings_after_deep_arrays_keep_depth_error(kind, ending):
    text = "[" * 1025 + "0" + "]" * 1024 + ending
    assert_first_error_is_unchanged(text, kind)


@pytest.mark.parametrize("kind", INPUT_KINDS)
@pytest.mark.parametrize("prefix", ["", " \n\t", " " * 128])
@pytest.mark.parametrize("suffix", ["", " \n\t", " " * 128])
@pytest.mark.parametrize("root", ["array", "object"])
def test_valid_large_containers_and_whitespace(kind, prefix, suffix, root):
    values = [None, True, False, 0, -1, 2**63, 2**64 - 1, -0.0, 1.25,
              "\u00e9\u2603\U0001f600" * 100, [], {}, {"a": [1, 2, 3]}]
    value = values if root == "array" else {"values": values, "empty": {}}
    text = prefix + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + suffix
    decoded = jsonmodem.loads(as_input(text, kind))
    assert decoded == value
    actual = decoded if root == "array" else decoded["values"]
    assert math.copysign(1, actual[7]) == -1


@pytest.mark.parametrize("kind", INPUT_KINDS)
def test_duplicate_keys_keep_last_value_in_large_valid_object(kind):
    text = '{"padding":"' + "x" * 2048 + '","key":1,"key":2}'
    assert jsonmodem.loads(as_input(text, kind)) == {"padding": "x" * 2048, "key": 2}


@pytest.mark.parametrize("kind", INPUT_KINDS[1:])
@pytest.mark.parametrize("invalid", [b"\xff", b"\xc0\x80", b"\xed\xa0\x80", b"\xf0\x9f"])
def test_invalid_utf8_precedes_an_earlier_json_error(kind, invalid):
    raw = b'["' + b"p" * 1100 + b'",01,' + invalid + b"}"
    value = memoryview(array("B", raw)) if kind == "array_view" else {
        "bytes": bytes, "bytearray": bytearray, "memoryview": memoryview,
    }[kind](raw)
    with pytest.raises(jsonmodem.JSONDecodeError) as error:
        jsonmodem.loads(value)
    assert error.value.msg == "str is not valid UTF-8"
    assert error.value.doc == ""
    assert (error.value.pos, error.value.lineno, error.value.colno) == (0, 1, 1)


@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff"])
def test_python_surrogates_precede_an_earlier_json_error(surrogate):
    text = '["' + "p" * 1100 + '",01,' + surrogate + "}"
    with pytest.raises(jsonmodem.JSONDecodeError) as error:
        jsonmodem.loads(text)
    assert error.value.msg == "str is not valid UTF-8"
    assert error.value.doc == ""
    assert (error.value.pos, error.value.lineno, error.value.colno) == (0, 1, 1)


@pytest.mark.parametrize("kind", INPUT_KINDS)
@pytest.mark.parametrize("parents", [1023, 1024])
@pytest.mark.parametrize("pattern", ["array", "object", "mixed"])
@pytest.mark.parametrize("leaf", ["[]", "{}", '{"broken" 0}'])
def test_empty_and_mixed_containers_at_depth_limit(kind, parents, pattern, leaf):
    openings = [
        '{"a":' if pattern == "object" or (pattern == "mixed" and index % 2) else "["
        for index in range(parents)
    ]
    closings = ["}" if opening.startswith("{") else "]" for opening in reversed(openings)]
    closings[-1] = "]" if closings[-1] == "}" else "}"
    text = "".join(openings) + leaf + "".join(closings)
    assert_first_error_is_unchanged(text, kind)
    with pytest.raises(jsonmodem.JSONDecodeError) as error:
        jsonmodem.loads(as_input(text, kind))
    assert (error.value.msg == "recursion depth exceeded") == (parents == 1024)


@pytest.mark.parametrize("kind", INPUT_KINDS)
@pytest.mark.parametrize("number", [
    "9" * 310, "-" + "9" * 310,
    "18446744073709551616", "-9223372036854775809",
])
def test_bare_integer_overflow_before_invalid_ending(kind, number):
    text = '["' + "p" * 1100 + '",' + number + "}"
    assert_first_error_is_unchanged(text, kind)


@pytest.mark.parametrize("kind", INPUT_KINDS)
@pytest.mark.parametrize("length", [1023, 1024, 1025])
def test_exact_byte_length_thresholds(kind, length):
    prefix, suffix = '["', '",01}'
    text = prefix + "p" * (length - len(prefix) - len(suffix)) + suffix
    assert len(text.encode()) == length
    assert_first_error_is_unchanged(text, kind)
