"""Character positions remain correct after long or multibyte input prefixes."""

from array import array
import gc
import json

import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")


def as_input(text, kind):
    if kind == "str":
        return text
    data = text.encode()
    if kind == "array_view":
        return memoryview(array("B", data))
    return {"bytes": bytes, "bytearray": bytearray, "memoryview": memoryview}[kind](data)


def fields(error):
    return error.msg, error.pos, error.lineno, error.colno, error.doc, str(error)


@pytest.mark.parametrize("character", ["x", "\u00e9", "\u2603", "\U0001f600"])
@pytest.mark.parametrize("length", [0, 1, 7, 8, 31, 32, 33, 255, 4096])
@pytest.mark.parametrize("kind", ["str", "bytes", "bytearray", "memoryview", "array_view"])
def test_trailing_error_after_long_unicode_prefix(character, length, kind):
    document = json.dumps({"value": character * length}, ensure_ascii=False)
    prefix = " \n\t" + document + "\n \t"
    text = prefix + "!"
    value = as_input(text, kind)
    errors = []
    for module in (jsonmodem, orjson):
        with pytest.raises(module.JSONDecodeError) as caught:
            module.loads(value)
        error = caught.value
        assert error.pos == len(prefix)
        assert error.lineno == prefix.count("\n") + 1
        assert error.colno == len(prefix) - prefix.rfind("\n")
        assert error.doc == text
        errors.append(fields(error))
    assert errors[0] == errors[1]


@pytest.mark.parametrize("tail", [
    '"unfinished', '"tail\\', '"tail\\u12', '"tail\\u12\u2603"',
    '"tail\\q"', '"tail\\uD800\\u1234"', "-", "1.", "1e+", "01", "true false",
])
@pytest.mark.parametrize("character", ["x", "\u00e9", "\u2603", "\U0001f600"])
def test_malformed_tail_position_moves_by_characters(tail, character):
    short_prefix = '[\n"",\n'
    long_prefix = '[\n"' + character * 4096 + '",\n'
    with pytest.raises(jsonmodem.JSONDecodeError) as short:
        jsonmodem.loads(short_prefix + tail)
    text = long_prefix + tail
    with pytest.raises(jsonmodem.JSONDecodeError) as long:
        jsonmodem.loads(text)
    error = long.value
    expected_position = short.value.pos + len(long_prefix) - len(short_prefix)
    assert error.msg == short.value.msg
    assert error.pos == expected_position
    assert error.lineno == text.count("\n", 0, expected_position) + 1
    assert error.colno == expected_position - text.rfind("\n", 0, expected_position)
    assert error.doc == text


@pytest.mark.parametrize("kind", ["bytearray", "memoryview", "array_view"])
def test_error_retains_original_document_after_input_changes(kind):
    text = '["' + "\u2603\U0001f600" * 4096 + '"]\n!'
    data = text.encode()
    owner = array("B", data) if kind == "array_view" else bytearray(data)
    value = owner if kind == "bytearray" else memoryview(owner)
    with pytest.raises(jsonmodem.JSONDecodeError) as caught:
        jsonmodem.loads(value)
    error = caught.value
    before = fields(error)
    replacement = b"0" * len(owner)
    owner[:] = array("B", replacement) if kind == "array_view" else replacement
    if isinstance(value, memoryview):
        value.release()
    del value, owner
    gc.collect()
    assert fields(error) == before
    assert error.doc == text
    assert error.pos == len(text) - 1
