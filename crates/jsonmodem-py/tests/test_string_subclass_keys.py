"""Dictionary-key acceptance and callback order compared with orjson."""

import dataclasses

import pytest
import jsonmodem

orjson = pytest.importorskip("orjson")

KEY_MODES = (
    0,
    orjson.OPT_SORT_KEYS,
    orjson.OPT_NON_STR_KEYS,
    orjson.OPT_SORT_KEYS | orjson.OPT_NON_STR_KEYS,
)
OTHER_OPTIONS = (
    0,
    orjson.OPT_INDENT_2,
    orjson.OPT_APPEND_NEWLINE,
    orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
    orjson.OPT_STRICT_INTEGER,
    orjson.OPT_PASSTHROUGH_SUBCLASS,
)
MISSING = object()


class Text(str):
    pass


class ReplacedText(str):
    def __str__(self):
        return "overridden text"

    def encode(self, *args, **kwargs):
        raise AssertionError("encode override")

    def __lt__(self, other):
        raise AssertionError("comparison override")


class RaisingText(str):
    def __str__(self):
        raise AssertionError("str override")

    def __repr__(self):
        raise AssertionError("repr override")


class Mapping(dict):
    def items(self):
        raise AssertionError("items override")

    def __iter__(self):
        raise AssertionError("iteration override")


class Marker:
    def __init__(self, name):
        self.name = name


@dataclasses.dataclass
class Record:
    z: object
    a: object
    _private: object


def placed(value, location):
    if location == "dict":
        return {"outer": value}
    if location == "list":
        return [value]
    return value


def outcome(module, value, option, default=MISSING):
    kwargs = {"option": option}
    if default is not MISSING:
        kwargs["default"] = default
    try:
        return "ok", module.dumps(value, **kwargs)
    except TypeError as error:
        message = str(error)
        # The libraries use different text for the same invalid-UTF-8 error.
        if message.startswith("str is not valid UTF-8"):
            message = "invalid UTF-8"
        cause = error.__cause__
        if isinstance(cause, UnicodeEncodeError):
            cause = (
                type(cause).__name__, str(cause),
                cause.encoding, cause.start, cause.end, cause.reason,
            )
        else:
            cause = None if cause is None else (type(cause).__name__, str(cause))
        return "error", type(error).__name__, message, cause


def expected_utf8_cause(text, start=0):
    # Keep the expected message independent of either serializer.
    reason = "surrogates not allowed"
    error = UnicodeEncodeError("utf-8", text, start, start + 1, reason)
    return "UnicodeEncodeError", str(error), "utf-8", start, start + 1, reason


@pytest.mark.parametrize("text_type", [Text, ReplacedText, RaisingText])
@pytest.mark.parametrize("location", ["root", "dict", "list"])
@pytest.mark.parametrize("key_mode", KEY_MODES)
@pytest.mark.parametrize("other_options", OTHER_OPTIONS)
def test_subclass_keys_require_non_str_keys(text_type, location, key_mode, other_options):
    option = key_mode | other_options
    value = placed({"z": 1, text_type("key\n\\\u00e9"): 2, "a": 3}, location)

    def default(obj):
        raise AssertionError("keys must not be passed to default")

    expected = outcome(orjson, value, option, default)
    if option & orjson.OPT_NON_STR_KEYS:
        plain = placed({"z": 1, "key\n\\\u00e9": 2, "a": 3}, location)
        assert expected == ("ok", orjson.dumps(plain, option=option))
    else:
        assert expected == ("error", "TypeError", "Dict key must be str", None)
    assert outcome(jsonmodem, value, option, default) == expected


@pytest.mark.parametrize("mapping_type", [dict, Mapping])
@pytest.mark.parametrize("option", KEY_MODES)
@pytest.mark.parametrize("key_first", [False, True])
@pytest.mark.parametrize("callback", ["absent", "return", "raise"])
def test_subclass_key_and_value_callback_order(mapping_type, option, key_first, callback):
    observations = []
    for module in (orjson, jsonmodem):
        calls = []
        pairs = [("z", Marker("before")), (Text("m"), Marker("key value"))]
        if key_first:
            pairs.reverse()
        value = mapping_type(pairs + [("a", 0)])

        def default(obj):
            assert type(obj) is Marker
            calls.append(obj.name)
            if callback == "raise":
                raise ValueError("callback failed")
            return 1

        result = outcome(module, value, option, MISSING if callback == "absent" else default)
        observations.append((result, calls))
    expected, calls = observations[0]
    if not option & orjson.OPT_NON_STR_KEYS:
        if key_first or option & orjson.OPT_SORT_KEYS:
            assert expected == ("error", "TypeError", "Dict key must be str", None)
            assert calls == []
        elif callback != "absent":
            assert calls == ["before"]
    assert observations[1] == observations[0]


@pytest.mark.parametrize("mapping_type", [dict, Mapping])
@pytest.mark.parametrize("option", KEY_MODES)
@pytest.mark.parametrize("invalid_first", [False, True])
def test_subclass_key_and_invalid_exact_key_order(mapping_type, option, invalid_first):
    pairs = [("\ud800", 1), (RaisingText("key"), 2)]
    if not invalid_first:
        pairs.reverse()
    value = mapping_type(pairs + [("tail", 3)])
    expected = outcome(orjson, value, option)
    message = "invalid UTF-8" if invalid_first or option & orjson.OPT_NON_STR_KEYS else "Dict key must be str"
    cause = expected_utf8_cause("\ud800") if message == "invalid UTF-8" else None
    assert expected == ("error", "TypeError", message, cause)
    assert outcome(jsonmodem, value, option) == expected


@pytest.mark.parametrize("mapping_type", [dict, Mapping])
@pytest.mark.parametrize("option", KEY_MODES)
def test_invalid_subclass_key_and_earlier_callback(mapping_type, option):
    observations = []
    for module in (orjson, jsonmodem):
        calls = []
        value = mapping_type([("z", Marker("before")), (Text("\ud800"), 1), ("a", 2)])

        def default(obj):
            calls.append(obj.name)
            return 0

        observations.append((outcome(module, value, option, default), calls))
    result, calls = observations[0]
    message = "invalid UTF-8" if option & orjson.OPT_NON_STR_KEYS else "Dict key must be str"
    cause = expected_utf8_cause("\ud800") if message == "invalid UTF-8" else None
    assert result == ("error", "TypeError", message, cause)
    assert calls == ([] if option & (orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS) else ["before"])
    assert observations[1] == observations[0]


@pytest.mark.parametrize("option", KEY_MODES)
@pytest.mark.parametrize("location", ["root", "list"])
@pytest.mark.parametrize("hidden", [False, True])
def test_dataclass_excludes_private_values_not_public_dictionary_keys(option, location, hidden):
    bad = {RaisingText("key"): 1}
    value = Record(3, {"z": 2, "a": 1} if hidden else bad, bad if hidden else Marker("hidden"))
    value = placed(value, location)

    def default(obj):
        raise AssertionError("excluded field must not call default")

    expected = outcome(orjson, value, option, default)
    if hidden or option & orjson.OPT_NON_STR_KEYS:
        assert expected[0] == "ok"
    else:
        assert expected == ("error", "TypeError", "Dict key must be str", None)
    assert outcome(jsonmodem, value, option, default) == expected


@pytest.mark.parametrize("option", KEY_MODES)
@pytest.mark.parametrize("field_name", ["a", "_private"])
def test_dataclass_attribute_names_require_exact_strings(option, field_name):
    observations = []
    for module in (orjson, jsonmodem):
        calls = []
        value = Record(Marker("before"), 1, 2)
        attributes = value.__dict__
        # A fresh dictionary avoids retaining the class's shared exact-str key.
        value.__dict__ = {key: item for key, item in attributes.items() if key != field_name}
        value.__dict__[Text(field_name)] = attributes[field_name]
        assert type(list(value.__dict__)[-1]) is Text

        def default(obj):
            calls.append(obj.name)
            return 0

        observations.append((outcome(module, value, option, default), calls))
    assert observations[0] == (("error", "TypeError", "Dict key must be str", None), ["before"])
    assert observations[1] == observations[0]


@pytest.mark.parametrize("option", KEY_MODES)
@pytest.mark.parametrize("dataclass", [False, True])
def test_callback_returned_dictionary_uses_the_same_key_policy(option, dataclass):
    observations = []
    if dataclass:
        option |= orjson.OPT_PASSTHROUGH_DATACLASS
    for module in (orjson, jsonmodem):
        calls = []
        value = Record(0, 1, 2) if dataclass else Marker("source")

        def default(obj):
            assert obj is value
            calls.append("default")
            return {"z": 1, RaisingText("m"): 2, "a": 3}

        observations.append((outcome(module, value, option, default), calls))
    assert observations[0][1] == ["default"]
    if not option & orjson.OPT_NON_STR_KEYS:
        assert observations[0][0] == ("error", "TypeError", "Dict key must be str", None)
    else:
        assert observations[0][0][0] == "ok"
    assert observations[1] == observations[0]


@pytest.mark.parametrize("sorted_keys", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_converted_subclass_keys_keep_duplicate_entries(sorted_keys, reverse):
    option = orjson.OPT_NON_STR_KEYS | (orjson.OPT_SORT_KEYS if sorted_keys else 0)
    pairs = [(RaisingText("1"), "subclass"), (1, "integer")]
    if reverse:
        pairs.reverse()
    value = dict(pairs)
    expected = b'{"1":"integer","1":"subclass"}' if reverse else b'{"1":"subclass","1":"integer"}'
    assert orjson.dumps(value, option=option) == expected
    assert jsonmodem.dumps(value, option=option) == expected


@pytest.mark.parametrize("text_type", [Text, ReplacedText, RaisingText])
@pytest.mark.parametrize("passthrough", [False, True])
def test_subclass_values_keep_their_existing_option_behavior(text_type, passthrough):
    option = orjson.OPT_PASSTHROUGH_SUBCLASS if passthrough else 0
    value = {"key": text_type("value")}
    observations = []
    for module in (orjson, jsonmodem):
        calls = []

        def default(obj):
            assert obj is value["key"]
            calls.append("default")
            return "converted"

        observations.append((outcome(module, value, option, default), calls))
    expected = b'{"key":"converted"}' if passthrough else b'{"key":"value"}'
    assert observations[0] == (("ok", expected), ["default"] if passthrough else [])
    assert observations[1] == observations[0]


@pytest.mark.parametrize("option", KEY_MODES)
@pytest.mark.parametrize("field_name", ["\ud800", "_\ud800"])
def test_dataclass_invalid_exact_attribute_name_follows_earlier_callback(option, field_name):
    observations = []
    for module in (orjson, jsonmodem):
        calls = []
        value = Record(Marker("before"), 1, 2)
        value.__dict__ = {
            "z": value.z, "a": value.a, "_private": value._private,
            field_name: Marker("invalid name value"),
        }
        last_key = list(value.__dict__)[-1]
        assert type(last_key) is str and last_key == field_name

        def default(obj):
            assert type(obj) is Marker
            calls.append(obj.name)
            return 0

        observations.append((outcome(module, value, option, default), calls))
    cause = expected_utf8_cause(field_name, len(field_name) - 1)
    assert observations[0] == (("error", "TypeError", "invalid UTF-8", cause), ["before"])
    assert observations[1] == observations[0]
