"""String access keeps output, fallback behavior and owning references unchanged."""

import dataclasses
import gc
import json
import sys

import pytest

import jsonmodem


PLACEMENTS = ("root", "list", "tuple", "dict_key", "dict_value")
OPTIONS = (
    0,
    jsonmodem.OPT_INDENT_2,
    jsonmodem.OPT_SORT_KEYS,
    jsonmodem.OPT_APPEND_NEWLINE | jsonmodem.OPT_NON_STR_KEYS | jsonmodem.OPT_STRICT_INTEGER,
)


def placed(text, placement):
    if placement == "root":
        return text
    if placement == "list":
        return [text, {"text": text}]
    if placement == "tuple":
        return (text, {"text": text})
    if placement == "dict_key":
        return {"padding": "p" * 2048, text: 1}
    if placement == "dict_value":
        return {"padding": "p" * 2048, "text": text}
    raise AssertionError(placement)


def expected_bytes(value, option=0):
    kwargs = {
        "ensure_ascii": False,
        "sort_keys": bool(option & jsonmodem.OPT_SORT_KEYS),
    }
    if option & jsonmodem.OPT_INDENT_2:
        kwargs["indent"] = 2
    else:
        kwargs["separators"] = (",", ":")
    output = json.dumps(value, **kwargs).encode()
    if option & jsonmodem.OPT_APPEND_NEWLINE:
        output += b"\n"
    return output


@pytest.mark.parametrize("codepoint", range(128))
@pytest.mark.parametrize("placement", ("root", "dict_key", "dict_value"))
def test_every_ascii_byte_keeps_its_length_and_escaping(codepoint, placement):
    text = "before" + chr(codepoint) + "after"
    value = placed(text, placement)
    assert jsonmodem.dumps(value) == expected_bytes(value)


@pytest.mark.parametrize("length", [0, 1, 7, 8, 63, 64, 65, 255, 256, 257, 1023, 1024, 1025, 65537])
@pytest.mark.parametrize("placement", PLACEMENTS)
@pytest.mark.parametrize("option", OPTIONS)
def test_ascii_lengths_across_output_and_key_cache_limits(length, placement, option):
    text = "a" * length
    value = placed(text, placement)
    assert jsonmodem.dumps(value, option=option) == expected_bytes(value, option)


@pytest.mark.parametrize("special", ['"', "\\", "\x00", "\n", "\x1f"])
@pytest.mark.parametrize("position", [0, 7, 63, 255, 1024, 65536])
@pytest.mark.parametrize("placement", ["root", "dict_key"])
def test_ascii_escape_after_long_plain_prefix(special, position, placement):
    text = "a" * position + special + "z"
    value = placed(text, placement)
    assert jsonmodem.dumps(value) == expected_bytes(value)


@pytest.mark.parametrize("text", ["\u00e9", "\u0100", "\u2603", "\U0001f600", "a\u00e9\u2603\U0001f600\x00\n"])
@pytest.mark.parametrize("placement", PLACEMENTS)
@pytest.mark.parametrize("option", OPTIONS)
def test_unicode_strings_keep_utf8_fallback(text, placement, option):
    value = placed(text * 129, placement)
    expected = expected_bytes(value, option)
    assert jsonmodem.dumps(value, option=option) == expected
    assert jsonmodem.dumps(value, option=option) == expected


@pytest.mark.parametrize("text", ["\ud800", "\udfff", "a\ud800", "\u00e9\udfff", "x" * 1024 + "\ud800"])
@pytest.mark.parametrize("placement", PLACEMENTS)
@pytest.mark.parametrize("option", [0, jsonmodem.OPT_SORT_KEYS])
def test_surrogates_keep_the_existing_encode_error(text, placement, option):
    with pytest.raises(TypeError, match="str is not valid UTF-8"):
        jsonmodem.dumps(placed(text, placement), option=option)


@pytest.mark.parametrize("text", ["", "ascii", "a\x00\n\\\"z", "\u00e9\u2603\U0001f600", "a" * 1024])
@pytest.mark.parametrize("placement", PLACEMENTS)
@pytest.mark.parametrize("option", [0, jsonmodem.OPT_INDENT_2 | jsonmodem.OPT_SORT_KEYS])
def test_string_subclasses_do_not_invoke_overrides(text, placement, option):
    class Text(str):
        """Overrides must not replace the inherited string storage."""

        def __str__(self):
            raise AssertionError("__str__ was called")

        def __len__(self):
            raise AssertionError("__len__ was called")

        def __getattribute__(self, name):
            raise AssertionError(f"attribute lookup: {name}")

    value = placed(Text(text), placement)
    assert jsonmodem.dumps(value, option=option) == expected_bytes(placed(text, placement), option)


@pytest.mark.parametrize("text", ["ascii", "a\x00z", "\u00e9\u2603", "a" * 1024])
def test_passthrough_string_subclass_still_calls_default(text):
    class Text(str):
        pass

    value = Text(text)
    calls = []

    def default(item):
        assert item is value
        calls.append(item)
        return "replacement"

    assert jsonmodem.dumps(value, default=default, option=jsonmodem.OPT_PASSTHROUGH_SUBCLASS) == b'"replacement"'
    assert calls == [value]


@pytest.mark.parametrize("key_count", [1, 16, 17, 80])
def test_ascii_key_owners_and_encoded_ranges_after_growth(key_count):
    keys = [f"escaped\n\x00\"key_{index}" for index in range(key_count)]
    value = ["p" * 2048, dict.fromkeys(keys, 0)]
    for length in (256, 4096, 65536):
        value.extend(["x" * length, dict.fromkeys(keys, length)])
    assert jsonmodem.dumps(value) == expected_bytes(value)


def test_equal_ascii_text_in_distinct_owners():
    raw = b"equal ascii keys with an embedded\x00byte"
    keys = [raw.decode() for _ in range(64)]
    assert len({id(key) for key in keys}) == len(keys)
    value = ["p" * 2048, [{key: index} for index, key in enumerate(keys)] * 4]
    assert jsonmodem.dumps(value) == expected_bytes(value)


@pytest.mark.parametrize("error_text", ["\ud800", "\u00e9\udfff", "x" * 1024 + "\ud800"])
def test_callback_clears_source_before_later_unicode_error(error_text):
    first = object()
    source = ["p" * 2048, first, error_text]
    calls = []

    def default(value):
        assert value is first
        calls.append(value)
        source.clear()
        gc.collect()
        assert jsonmodem.dumps("inner\x00text") == b'"inner\\u0000text"'
        return "replacement"

    with pytest.raises(TypeError, match="str is not valid UTF-8"):
        jsonmodem.dumps(source, default=default)
    assert calls == [first]
    assert source == []


def test_callback_restarts_after_ascii_keys_and_reenters_encoder():
    first, last = object(), object()
    keys = [f"owned_ascii_key_{index}" for index in range(32)]
    source = dict.fromkeys(keys, "ascii\x00value")
    source["first"] = first
    source["last"] = last
    expected = ["p" * 2048, {**source, "first": {"inner": "a\x00z"}, "last": "last value"}]
    calls = []

    def default(value):
        calls.append(value)
        source.clear()
        if value is first:
            return jsonmodem.Fragment(jsonmodem.dumps({"inner": "a\x00z"}))
        assert value is last
        return "last value"

    assert jsonmodem.dumps(["p" * 2048, source], default=default) == expected_bytes(expected)
    assert calls == [first, last]


@pytest.mark.skipif(
    sys.implementation.name != "cpython" or bool(getattr(sys, "_is_gil_enabled", lambda: True)()) is False,
    reason="checks GIL-enabled CPython reference counts",
)
@pytest.mark.parametrize("suffix", ["", "\x00\n", "\u00e9"])
def test_checked_key_cache_keeps_field_owners(suffix):
    @dataclasses.dataclass
    class Record:
        pass

    record = Record()
    names = [f"field_{index}{suffix}" for index in range(17)]
    # Avoid references retained by CPython's shared instance-key table.
    record.__dict__ = dict(zip(names, range(17)))
    marker = object()
    value = ["p" * 2048, record, marker]
    expected = [value[0], dict(zip(names, range(17))), None]
    references = [sys.getrefcount(name) for name in names]
    calls = []

    def default(item):
        assert item is marker
        calls.append(item)
        record.__dict__.clear()
        assert [sys.getrefcount(name) for name in names] == [
            count - int(index == 16) for index, count in enumerate(references)
        ]
        return None

    assert jsonmodem.dumps(value, default=default) == expected_bytes(expected)
    assert calls == [marker]
    assert [sys.getrefcount(name) for name in names] == [count - 1 for count in references]
