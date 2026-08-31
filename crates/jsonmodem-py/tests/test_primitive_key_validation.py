"""Primitive keys keep conversion order and key errors before value callbacks."""

import enum

import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")

OPTIONS = (
    orjson.OPT_NON_STR_KEYS,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_STRICT_INTEGER,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_INDENT_2,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_APPEND_NEWLINE,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_PASSTHROUGH_SUBCLASS,
    orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS,
)


def placed(value, location):
    if location == "dict":
        return {"outer": value}
    if location == "list":
        return [value]
    return value


def error_signature(library, value, option, default):
    with pytest.raises(TypeError) as caught:
        library.dumps(value, option=option, default=default)
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


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("location", ["root", "dict", "list"])
def test_primitive_keys_and_converted_duplicates(option, location):
    value = [
        {None: 1, "null": 2, True: 3, "true": 4, False: 5, "false": 6},
        {1: 1, "1": 2, -7: 3, "-7": 4, 1.25: 5, "1.25": 6},
        {2**64 - 1: 1, -(2**63): 2, 2**53: 3},
        {-0.0: 1, "-0.0": 2},
        {float("inf"): 1, float("-inf"): 2, float("nan"): 3, "null": 4},
        {"key\n\\\u00e9": 1, 42: 2, "42": 3},
    ]
    value = placed(value, location)
    assert jsonmodem.dumps(value, option=option) == orjson.dumps(value, option=option)


@pytest.mark.parametrize("location", ["root", "dict", "list"])
@pytest.mark.parametrize(
    "invalid_key",
    [
        pytest.param(2**64, id="unsigned-key-overflow"),
        pytest.param(-(2**63) - 1, id="signed-key-overflow"),
        pytest.param("z\ud800", id="invalid-utf8-key"),
        pytest.param(("z",), id="unsupported-key"),
    ],
)
@pytest.mark.parametrize("earlier", ["wide-value", "strict-value", "callback", "raising-callback"])
def test_primitive_keys_are_checked_before_values(location, invalid_key, earlier):
    observations = []
    for library in (orjson, jsonmodem):
        calls = []
        marker = object()
        option = library.OPT_NON_STR_KEYS
        if earlier == "wide-value":
            value = 2**64
        elif earlier == "strict-value":
            value = 2**53
            option |= library.OPT_STRICT_INTEGER
        else:
            value = marker

        def default(obj):
            assert obj is marker
            calls.append("default")
            if earlier == "raising-callback":
                raise ValueError("default failed")
            return 9

        expected = error_signature(library, {invalid_key: 0}, option, default)
        combined = placed({17: value, invalid_key: 0, "tail": 2}, location)
        actual = error_signature(library, combined, option, default)
        assert actual == expected
        assert calls == []
        observations.append(actual)
    assert observations[0] == observations[1]


@pytest.mark.parametrize("location", ["root", "list"])
@pytest.mark.parametrize("strict", [False, True])
def test_primitive_keys_keep_enum_fallback_and_callback(location, strict):
    class Number(enum.Enum):
        entry = 7

    observations = []
    for library in (orjson, jsonmodem):
        calls = []
        marker = object()
        option = library.OPT_NON_STR_KEYS
        if strict:
            option |= library.OPT_STRICT_INTEGER
        value = placed({2**64 - 1: 1, Number.entry: 2, "value": marker}, location)

        def default(obj):
            assert obj is marker
            calls.append("default")
            return 3

        output = library.dumps(value, option=option, default=default)
        assert calls == ["default"]
        observations.append(output)
    assert observations[0] == observations[1]
