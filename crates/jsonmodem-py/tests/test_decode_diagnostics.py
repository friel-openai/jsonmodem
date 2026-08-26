"""Error positions and messages are part of the complete-document API."""

import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")


@pytest.mark.parametrize("token", [
    r'"\u"', r'"\u0"', r'"\u00"', r'"\u000"', r'"\u000x"',
    r'"\uDC00"', r'"\uDFFF"', r'"\uD800"', r'"\uD800x"',
    r'"\uD800\u1234"', r'"\uD800\uZZZZ"', r'"\uD800\uD800"', r'"\q"',
])
@pytest.mark.parametrize("context", ["{}", '["\u00e9",{}]', '{{\n"value": {}}}'])
@pytest.mark.parametrize("input_type", [str, bytes, bytearray, memoryview])
def test_unicode_escape_diagnostics(token, context, input_type):
    text = context.format(token)
    value = text if input_type is str else input_type(text.encode())
    errors = []
    for module in (jsonmodem, orjson):
        with pytest.raises(module.JSONDecodeError) as caught:
            module.loads(value)
        error = caught.value
        errors.append((error.msg, error.pos, error.lineno, error.colno, error.doc))
    assert errors[0] == errors[1]


@pytest.mark.parametrize("document", ['{"value":1}', '["\u00e9"]', '"\u2603"', '123'])
@pytest.mark.parametrize("separator", ["", " ", "\n\t"])
def test_trailing_content_position_can_trim_document(document, separator):
    text = document + separator + "; trailing"
    errors = []
    for module in (jsonmodem, orjson):
        with pytest.raises(module.JSONDecodeError) as caught:
            module.loads(text)
        error = caught.value
        assert module.loads(text[:error.pos]) == module.loads(document)
        errors.append((error.msg, error.pos, error.lineno, error.colno))
    assert errors[0] == errors[1]
