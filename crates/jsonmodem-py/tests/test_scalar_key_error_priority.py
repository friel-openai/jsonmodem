"""Key options decide whether an invalid key precedes an earlier scalar error."""

import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")

KEY_MODES = (
    pytest.param(0, id="no-key-options"),
    pytest.param(orjson.OPT_SORT_KEYS, id="sort-keys"),
    pytest.param(orjson.OPT_NON_STR_KEYS, id="non-str-keys"),
    pytest.param(orjson.OPT_SORT_KEYS | orjson.OPT_NON_STR_KEYS, id="both-key-options"),
)


def placed(value, location):
    if location == "dict":
        return {"outer": value}
    if location == "list":
        return [value]
    return value


def error_outcome(module, value, option):
    with pytest.raises(TypeError) as caught:
        module.dumps(value, option=option)
    error = caught.value
    cause = error.__cause__
    if isinstance(cause, UnicodeEncodeError):
        cause = (
            type(cause).__name__, str(cause), cause.encoding, cause.object,
            cause.start, cause.end, cause.reason,
        )
    elif cause is not None:
        cause = type(cause).__name__, str(cause)
    return type(error).__name__, str(error), cause


@pytest.mark.parametrize("location", ["root", "dict", "list"])
@pytest.mark.parametrize("key_mode", KEY_MODES)
@pytest.mark.parametrize(
    "invalid_key",
    [
        pytest.param("z\ud800", id="invalid-utf8"),
        pytest.param(("z",), id="tuple-key"),
    ],
)
@pytest.mark.parametrize(
    "scalar,extra_option,message",
    [
        pytest.param(2**64, 0, "Integer exceeds 64-bit range", id="unsigned-overflow"),
        pytest.param(-(2**63) - 1, 0, "Integer exceeds 64-bit range", id="signed-overflow"),
        pytest.param(
            2**53, orjson.OPT_STRICT_INTEGER, "Integer exceeds 53-bit range",
            id="strict-integer",
        ),
    ],
)
def test_exact_scalar_error_before_invalid_key(
    location, key_mode, invalid_key, scalar, extra_option, message,
):
    option = key_mode | extra_option
    for module in (orjson, jsonmodem):
        value_error = error_outcome(module, placed({"a": scalar}, location), option)
        key_error = error_outcome(module, placed({invalid_key: 0}, location), option)
        assert value_error[:2] == ("TypeError", message), module.__name__
        assert value_error != key_error, module.__name__

        # Each key option validates all keys first. Without either option, the
        # earlier value fails first. Compare full messages and causes unchanged.
        expected = key_error if key_mode else value_error
        combined = placed({"a": scalar, invalid_key: 0}, location)
        assert error_outcome(module, combined, option) == expected, module.__name__
