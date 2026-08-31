"""Preserve string values, ownership, singleton reuse and syntax failures."""

import gc
import json
import sys

import pytest

import jsonmodem

orjson = pytest.importorskip("orjson")

LENGTHS = (
    0, 1, 2, 3, 7, 8, 9, 15, 16, 17, 31, 32, 33, 47, 48, 49,
    63, 64, 65, 127, 128, 255, 256, 257,
)
OFFSETS = (0, 1, 7, 15, 16, 31, 32)


def inputs(document):
    raw = document.encode("utf-8")
    return document, raw, bytearray(raw), memoryview(raw)


def compare(document, expected):
    for argument in inputs(document):
        reference = orjson.loads(argument)
        actual = jsonmodem.loads(argument)
        assert actual == reference == expected
        assert type(actual) is type(reference)


@pytest.mark.parametrize("length", LENGTHS)
@pytest.mark.parametrize("offset", OFFSETS)
def test_ascii_characters_at_scan_boundaries(length, offset):
    values = [chr(codepoint) * length for codepoint in range(128)]
    expected = [values, {value: index for index, value in enumerate(values)}]
    document = " " * offset + json.dumps(expected, ensure_ascii=False)
    compare(document, expected)
    for value in jsonmodem.loads(document)[0]:
        assert type(value) is str
        assert value.encode("ascii").decode("ascii") == value


@pytest.mark.parametrize("length", LENGTHS)
@pytest.mark.parametrize("character", [
    "\u0080", "\u00e9", "\u0800", "\uffff", "\U00010000", "\U0010ffff",
])
def test_unicode_before_and_after_ascii_delimiters(length, character):
    plain = "x" * length
    expected = [plain, character, plain + character, character + plain,
                {plain: character, character: plain}, plain]
    for ensure_ascii in (False, True):
        compare(json.dumps(expected, ensure_ascii=ensure_ascii), expected)


@pytest.mark.parametrize("length", [0, 7, 8, 15, 16, 31, 32, 47, 48, 63, 64, 65])
@pytest.mark.parametrize("body,value", [
    ("", ""),
    (r'\"\\\/', '"\\/'),
    (r"\b\f\n\r\t", "\b\f\n\r\t"),
    (r"\u0000", "\0"),
    (r"\u007f", "\u007f"),
    (r"\u0080", "\u0080"),
    (r"\u00e9", "\u00e9"),
    (r"\u0800", "\u0800"),
    (r"\ud83d\ude42", "\U0001f642"),
    (r"\u005c\u006e", "\\n"),
    ("\u00e9" + r"\n", "\u00e9\n"),
    (r"\n" + "\U0001f642" + r"\t", "\n\U0001f642\t"),
])
def test_escape_classification_and_adjacent_runs(length, body, value):
    plain = "x" * length
    token = '"' + plain + body + plain + '"'
    expected_value = plain + value + plain
    document = '[' + token + ',{' + token + ':' + token + '},"\u00e9","after"]'
    compare(document, [expected_value, {expected_value: expected_value}, "\u00e9", "after"])


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython singleton preservation")
@pytest.mark.parametrize("text", ["", *map(chr, range(128)), "\u00e9", "\u00ff"])
def test_empty_and_single_character_identity_is_preserved(text):
    raw = json.dumps(text, ensure_ascii=False)
    escaped = json.dumps(text, ensure_ascii=True)
    document = '[' + raw + ',' + escaped + ',{' + raw + ':' + escaped + '}]'
    for argument in inputs(document):
        actual = jsonmodem.loads(argument)
        assert actual == orjson.loads(argument) == [text, text, {text: text}]
        key = next(iter(actual[2]))
        assert actual[0] is actual[1] is key is actual[2][key]
        assert jsonmodem.loads(raw) is actual[0]


@pytest.mark.parametrize("length", [2, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 4096])
def test_strings_outlive_mutable_and_released_inputs(length):
    text = "x" * length + "\0\n\t\\\""
    expected = [text, {text: text}, "\u00e9", "\u2603", "\U0001f642"]
    owner = bytearray(json.dumps(expected, ensure_ascii=True).encode())
    view = memoryview(owner)
    actual = jsonmodem.loads(view)
    view.release()
    owner[:] = b" " * len(owner)
    del owner
    assert actual == expected
    with pytest.raises(jsonmodem.JSONDecodeError):
        jsonmodem.loads(view)


@pytest.mark.parametrize(
    "large", ["x\n" * 32769, "\u00e9\n" * 21846],
    ids=["large_ascii_escapes", "large_unicode_escapes"],
)
def test_metadata_does_not_outlive_reused_or_released_escape_storage(large):
    expected = [large, "\u00e9", "\0", "ASCII", {"\n": "\u007f"}, "", "tail"]
    document = json.dumps(expected, ensure_ascii=True)
    compare(document, expected)
    assert jsonmodem.loads('["next","\\u0000","\\u00e9"]') == ["next", "\0", "\u00e9"]


def test_strings_are_initialized_when_gc_reenters_decoding():
    text = "decoded-ascii-value\0\n\t"
    expected = [[text, {"decoded-ascii-key": index}] for index in range(400)]
    document = json.dumps(expected)
    calls = []
    decoded_strings = []
    failures = []
    busy = False
    decoding = False

    def inspect_and_decode(phase, _info):
        nonlocal busy
        if phase != "start" or busy or not decoding:
            return
        busy = True
        try:
            for value in gc.get_objects():
                if type(value) is list and len(value) == 2:
                    first = value[0]
                    if type(first) is str and first.startswith("decoded-ascii-value"):
                        assert first == text
                        assert hash(first) == hash(text)
                        assert first.encode("ascii") == text.encode("ascii")
                        if first is not text:
                            decoded_strings.append(first)
            assert jsonmodem.loads('["nested-ascii", "\\u0000"]') == ["nested-ascii", "\0"]
            calls.append(True)
        except BaseException as error:
            failures.append(error)
        finally:
            busy = False

    thresholds = gc.get_threshold()
    gc.collect()
    gc.callbacks.append(inspect_and_decode)
    try:
        gc.set_threshold(50, 5, 5)
        decoding = True
        actual = jsonmodem.loads(document)
    finally:
        decoding = False
        gc.callbacks.remove(inspect_and_decode)
        gc.set_threshold(*thresholds)
    assert calls
    assert decoded_strings
    assert not failures, failures
    assert actual == expected


@pytest.mark.parametrize("leading", ["a", "\u00e9"])
@pytest.mark.parametrize("tail,message,relative_position", [
    ("", "unterminated string", 0),
    ("\\", "incomplete escape", 1),
    ('\\q"', "invalid escaped character in string", 1),
    ('\\u"', "invalid escaped sequence in string", 0),
    ('\\u00x0"', "invalid escaped sequence in string", 0),
    ('\\uD800"', "no low surrogate in string", 6),
    ('\\uD800\\q"', "no low surrogate in string", 6),
    ('\\uD800\\uZZZZ"', "invalid escaped sequence in string", 6),
    ('\\uD800\\u0000"', "invalid low surrogate in string", 6),
    ('\\uDC00"', "invalid high surrogate in string", 0),
    ("\\uD83D\\uDE42\\", "incomplete escape", 13),
    ('\n"', "unescaped control character", 0),
    ("\\u0000", "unterminated string", 6),
])
def test_string_errors_preserve_message_document_and_character_position(leading, tail, message, relative_position):
    head = '"' + leading + r"\n\t"
    document = head + tail
    expected = json.JSONDecodeError(message, document, len(head) + relative_position)
    for argument in inputs(document):
        with pytest.raises(orjson.JSONDecodeError):
            orjson.loads(argument)
        with pytest.raises(jsonmodem.JSONDecodeError) as caught:
            jsonmodem.loads(argument)
        error = caught.value
        assert (error.msg, error.doc, error.pos, error.lineno, error.colno) == (
            expected.msg, expected.doc, expected.pos, expected.lineno, expected.colno,
        )
        assert jsonmodem.loads('["after", "\\u007f"]') == ["after", "\u007f"]


@pytest.mark.parametrize("raw", [
    b'"ASCII"\xff',
    b'["ASCII", "\xc0\x80"]',
    b'{"ASCII":"\xed\xa0\x80"}',
    b'["' + b'x' * 64 + b'", "\xf4\x90\x80\x80"]',
])
def test_string_classification_does_not_replace_complete_utf8_validation(raw):
    for argument in (raw, bytearray(raw), memoryview(raw)):
        with pytest.raises(orjson.JSONDecodeError):
            orjson.loads(argument)
        with pytest.raises(jsonmodem.JSONDecodeError) as caught:
            jsonmodem.loads(argument)
        assert caught.value.msg == "str is not valid UTF-8"
        assert caught.value.pos == 0
