"""Keep long string prefixes exact across fixed-size copy boundaries."""

import json

import jsonmodem
import pytest

try:
    import orjson
except ModuleNotFoundError as error:
    if error.name != "orjson":
        raise
    orjson = None


@pytest.mark.parametrize(
    "length",
    (0, 1, 31, 32, 63, 64, 1023, 1024, 1025, 2047, 2048, 2049, 147456, 1048576),
)
@pytest.mark.parametrize("character", ("x", "\u00e9"))
@pytest.mark.parametrize("suffix", ("\n", '"', "\\", "\x00", "\x1f", "\U0001f642\n"))
@pytest.mark.parametrize("append_newline", (False, True))
def test_escaped_suffix_after_plain_prefix(length, character, suffix, append_newline):
    value = character * length + suffix
    ours_option = jsonmodem.OPT_APPEND_NEWLINE if append_newline else 0

    encoded = jsonmodem.dumps(value, option=ours_option)

    assert type(encoded) is bytes
    expected = json.dumps(value, ensure_ascii=False).encode("utf-8")
    if append_newline:
        expected += b"\n"
    assert encoded == expected
    if orjson is not None:
        reference_option = orjson.OPT_APPEND_NEWLINE if append_newline else 0
        assert encoded == orjson.dumps(value, option=reference_option)
