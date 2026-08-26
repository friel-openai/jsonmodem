"""Decoded values and cached keys must not borrow reusable string storage."""

import json

import pytest

import jsonmodem


@pytest.mark.parametrize("count", [1, 1000])
def test_escaped_values_and_keys_remain_independent(count):
    document = "[" + ",".join(
        r'{"\u0061":"first\nvalue","\u0062":"\ud83d\ude42","plain":"last\tvalue"}'
        for _ in range(count)
    ) + "]"
    assert jsonmodem.loads(document) == json.loads(document)


def test_unique_escaped_keys_past_cache_capacity():
    keys = [f"key-{index}\n\t\"\u2603" for index in range(600)]
    values = [{key: f"value-{index}\n\t"} for index, key in enumerate(keys)]
    values += [{key: "repeated\nvalue"} for key in reversed(keys)]
    document = json.dumps(values, ensure_ascii=True)
    assert jsonmodem.loads(document) == values


def test_escaped_and_plain_keys_have_the_same_duplicate_semantics():
    document = "[" + ",".join(
        r'{"first":0,"\u0066irst":1,"\u0073econd":2,"second":3}'
        for _ in range(1000)
    ) + "]"
    assert jsonmodem.loads(document) == [{"first": 1, "second": 3}] * 1000


@pytest.mark.parametrize("length", [65532, 65536, 65540, 1048576])
def test_large_escaped_token_release_preserves_values_and_keys(length):
    text = "x" * length + "\n\u2603"
    value = [text, {text: "short\nvalue"}, "plain", "last\tvalue"]
    assert jsonmodem.loads(json.dumps(value, ensure_ascii=True)) == value


@pytest.mark.parametrize("length", [0, 1, 7, 8, 15, 16, 31, 32, 63, 64, 65, 1024])
def test_escaped_values_change_length_and_encoding(length):
    values = [
        "x" * length + "\n",
        "\u2603" * length + "\t",
        "\U0001f642" * length + "\"",
        "",
        "plain",
        "\0",
    ]
    assert jsonmodem.loads(json.dumps(values, ensure_ascii=True)) == values


@pytest.mark.parametrize("length", [7, 8, 15, 16, 31, 32, 63, 64, 128])
@pytest.mark.parametrize("ensure_ascii", [False, True])
def test_streaming_strings_at_every_split(length, ensure_ascii):
    value = "x" * length + '\u2603\U0001f642\n\t\\"' + "y" * length
    document = json.dumps(value, ensure_ascii=ensure_ascii)
    for split in range(len(document) + 1):
        parser = jsonmodem.JsonModem()
        events = list(parser.feed(document[:split]))
        events.extend(parser.feed(document[split:]))
        events.extend(parser.finish())
        fragments = [event[2]["fragment"] for event in events if event[0] == "string"]
        assert "".join(fragments) == value

        values = jsonmodem.JsonModemValues()
        list(values.feed(document[:split]))
        list(values.feed(document[split:]))
        list(values.finish())
        assert values.view().snapshot() == value


@pytest.mark.parametrize("prefix", [0, 29, 30, 31, 32, 33, 127])
@pytest.mark.parametrize("length", [63, 126, 127, 128, 4096])
@pytest.mark.parametrize("character", ["x", "\u00e9", "\u2603", "\U0001f642"])
def test_unicode_validation_selection_preserves_values(prefix, length, character):
    value = "x" * prefix + character * length + "\n"
    for document in (
        json.dumps(value, ensure_ascii=False),
        json.dumps([value, {value: value}], ensure_ascii=False),
    ):
        expected = json.loads(document)
        encoded = (" \t\r\n" + document + " \t\r\n").encode()
        for input_value in (encoded, bytearray(encoded), memoryview(encoded)):
            assert jsonmodem.loads(input_value) == expected


@pytest.mark.parametrize("offset", [0, 1, 7, 15, 16, 31, 32, 33, 63, 64, 127, 128])
def test_invalid_utf8_keeps_decode_error(offset):
    invalid_sequences = [bytes([byte]) for byte in range(0x80, 0x100)] + [
        b"\xc0\x80", b"\xc1\xbf", b"\xe0\x80\x80", b"\xed\xa0\x80",
        b"\xf0\x80\x80\x80", b"\xf4\x90\x80\x80", b"\xf5\x80\x80\x80",
        b"\xc2", b"\xe2\x98", b"\xf0\x9f\x99",
    ]
    for invalid in invalid_sequences:
        document = b'"' + b"x" * offset + invalid + b"\xe2\x98\x83" * 128 + b'"'
        for input_value in (document, bytearray(document), memoryview(document)):
            with pytest.raises(jsonmodem.JSONDecodeError, match="valid UTF-8") as error:
                jsonmodem.loads(input_value)
            assert error.value.doc == ""
            assert error.value.pos == 0


@pytest.mark.parametrize("codepoint", [0x7F, 0x80, 0x7FF, 0x800, 0xD7FF, 0xE000, 0xFFFF, 0x10000, 0x10FFFF])
def test_utf8_codepoint_boundaries(codepoint):
    value = chr(codepoint) * 129
    document = json.dumps(value, ensure_ascii=False).encode()
    assert jsonmodem.loads(document) == value
    for length in range(1, min(5, len(document))):
        truncated = document[:-length]
        with pytest.raises(jsonmodem.JSONDecodeError):
            jsonmodem.loads(truncated)


def test_unicode_result_outlives_mutable_input():
    expected = "\u2603\U0001f642\u00e9" * 129
    owner = bytearray(json.dumps(expected, ensure_ascii=False).encode())
    view = memoryview(owner)
    value = jsonmodem.loads(view)
    view.release()
    owner[:] = b"x" * len(owner)
    del owner
    assert value == expected
