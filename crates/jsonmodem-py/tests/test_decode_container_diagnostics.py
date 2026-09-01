"""Container separator errors agree with the complete-document reference."""

import jsonmodem
import pytest

orjson = pytest.importorskip("orjson")


@pytest.mark.parametrize("value", ["null", "true", "0", '"text"', "[]", "{}"])
@pytest.mark.parametrize("container", ["array", "object"])
@pytest.mark.parametrize("ending", ["missing_comma", "wrong_closer", "eof", "space_eof"])
@pytest.mark.parametrize("prefix,padding", [("", ""), ("\n\t", ""), ("", "x" * 1100)])
@pytest.mark.parametrize("input_type", [str, bytes, bytearray, memoryview])
def test_container_separator_diagnostics(value, container, ending, prefix, padding, input_type):
    if container == "array":
        text = '["\u00e9' + padding + '",' + value
        suffix = {
            "missing_comma": " false]",
            "wrong_closer": "}",
            "eof": "",
            "space_eof": " \n\t",
        }[ending]
    else:
        text = '{"\u00e9' + padding + '":' + value
        suffix = {
            "missing_comma": ' "y":false}',
            "wrong_closer": "]",
            "eof": "",
            "space_eof": " \n\t",
        }[ending]
    # Long keys/values also exercise the large-invalid-ending validator.
    text = prefix + text + suffix
    document = text if input_type is str else input_type(text.encode())
    errors = []
    for module in (jsonmodem, orjson):
        with pytest.raises(module.JSONDecodeError) as caught:
            module.loads(document)
        error = caught.value
        errors.append((error.msg, error.pos, error.lineno, error.colno, error.doc))
    assert errors[0] == errors[1]
