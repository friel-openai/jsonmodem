"""Preserve complete output when several escapes share one scan block."""

import gc
import json

import pytest

import jsonmodem

try:
    import orjson
except ModuleNotFoundError as error:
    if error.name != "orjson":
        raise
    orjson = None


ESCAPES = tuple(chr(byte) for byte in range(32)) + ('"', "\\")
OPTIONS = (0, 1, 1024, 1025)


def expected_bytes(value, option=0):
    indent = 2 if option & jsonmodem.OPT_INDENT_2 else None
    separators = (",", ": ") if indent else (",", ":")
    encoded = json.dumps(
        value, ensure_ascii=False, indent=indent, separators=separators
    ).encode("utf-8")
    if option & jsonmodem.OPT_APPEND_NEWLINE:
        encoded += b"\n"
    if orjson is not None:
        assert encoded == orjson.dumps(value, option=option)
    return encoded


@pytest.mark.parametrize("escape", ESCAPES)
@pytest.mark.parametrize("prefix", (0, 7, 15, 16, 31))
@pytest.mark.parametrize("gap", (0, 1, 14, 15, 16, 17, 31, 32))
def test_every_escape_at_group_boundaries(escape, prefix, gap):
    value = "x" * prefix + escape + "y" * gap + escape + "tail" * 16
    assert jsonmodem.dumps(value) == expected_bytes(value)


@pytest.mark.parametrize("length", (0, 1, 7, 8, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256, 257, 1023, 1024, 1025))
@pytest.mark.parametrize("placement", ("early", "late", "dense"))
@pytest.mark.parametrize("option", OPTIONS)
def test_root_lengths_and_options(length, placement, option):
    if placement == "early":
        value = ("\n\"" + "x" * length)[:length]
    elif placement == "late":
        value = ("x" * length + "\n\"")[-length:] if length else ""
    else:
        value = ("\n\"\\\x00" * ((length + 3) // 4))[:length]
    assert len(value) == length
    assert jsonmodem.dumps(value, option=option) == expected_bytes(value, option)


@pytest.mark.parametrize("first", ('"', "\\", "\n", "\r", "\t", "\b", "\f", "\x00", "\x1f"))
@pytest.mark.parametrize("second", ('"', "\\", "\n", "\r", "\t", "\b", "\f", "\x00", "\x1f"))
@pytest.mark.parametrize("gap", (0, 1, 7, 14, 15, 16))
def test_ordered_escape_pairs(first, second, gap):
    value = "prefix-" + first + "x" * gap + second + "suffix" * 16
    assert jsonmodem.dumps(value) == expected_bytes(value)


@pytest.mark.parametrize("character", ("\u00e9", "\u2603", "\U0001f600"))
@pytest.mark.parametrize("alignment", range(17))
@pytest.mark.parametrize("context", ("root", "list", "value", "key"))
@pytest.mark.parametrize("option", OPTIONS)
def test_multibyte_text_across_blocks(character, alignment, context, option):
    text = "x" * alignment + "\x00\n" + character * 8 + "\"\\" + character * 16
    if context == "root":
        value = text
    elif context == "list":
        value = [text, [text], None]
    elif context == "value":
        value = {"before": text, "child": {"after": text}}
    else:
        value = {text: text, "child": {text: text}}
    assert jsonmodem.dumps(value, option=option) == expected_bytes(value, option)


@pytest.mark.parametrize("option", OPTIONS)
def test_key_cache_reuses_complete_escaped_bytes(option):
    keys = [f"key-{index}\n\"\x00" + "tail" * 8 for index in range(20)]
    value = [{key: "\n\"\\\x00" * 16 for key in keys} for _ in range(8)]
    assert jsonmodem.dumps(value, option=option) == expected_bytes(value, option)


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("kind", ("list", "dict"))
def test_callback_restart_keeps_owning_snapshot(option, kind):
    text = "\n\"\\\x00\u2603\U0001f600" * 32
    unknown = object()
    before = [text, unknown, text] if kind == "list" else {"before": text, "default": unknown, "after": text}
    expected = [text, "converted", text] if kind == "list" else {"before": text, "default": "converted", "after": text}
    calls = []

    def default(value):
        assert value is unknown
        calls.append(value)
        before.clear()
        gc.collect()
        assert jsonmodem.dumps(text) == expected_bytes(text)
        return "converted"

    assert jsonmodem.dumps(before, default=default, option=option) == expected_bytes(expected, option)
    assert calls == [unknown]


@pytest.mark.parametrize("raw", (b'"unchanged\\n"', b'{"value":"\\u0000"}', b"\xff", b""))
def test_raw_fragment_is_not_escaped(raw):
    text = "\n\"\\\x00" * 64
    assert jsonmodem.dumps([jsonmodem.Fragment(raw), text]) == b"[" + raw + b"," + expected_bytes(text) + b"]"


@pytest.mark.parametrize("option", OPTIONS)
def test_default_error_preserves_cause(option):
    error = ValueError("conversion failed")

    def default(value):
        raise error

    with pytest.raises(jsonmodem.JSONEncodeError) as caught:
        jsonmodem.dumps(["\n\"\\\x00" * 64, object()], default=default, option=option)
    assert caught.value.__cause__ is error


@pytest.mark.parametrize("surrogate", ("\ud800", "\udfff"))
@pytest.mark.parametrize("position", (0, 15, 16, 31, 32, 255, 256))
def test_surrogates_still_fail(surrogate, position):
    value = "\n\"" * position + surrogate + "\n\"" * 32
    with pytest.raises(jsonmodem.JSONEncodeError):
        jsonmodem.dumps(value)
    if orjson is not None:
        with pytest.raises(orjson.JSONEncodeError):
            orjson.dumps(value)


def test_cycle_and_depth_after_escaped_values():
    text = "\n\"\\\x00" * 64
    cyclic = [text]
    cyclic.append(cyclic)
    try:
        with pytest.raises(jsonmodem.JSONEncodeError):
            jsonmodem.dumps(cyclic)
    finally:
        cyclic.clear()
    nested = text
    for _ in range(256):
        nested = [nested]
    with pytest.raises(jsonmodem.JSONEncodeError):
        jsonmodem.dumps(nested)
