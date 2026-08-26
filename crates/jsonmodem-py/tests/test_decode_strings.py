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
