"""Adjacent escapes preserve decoded values, owned strings and exact errors."""

import json

import pytest

import jsonmodem

try:
    import orjson
except ImportError:
    orjson = None


SIMPLE_ESCAPES = [
    pytest.param(r'\"', '"', id="quote"),
    pytest.param(r"\\", "\\", id="backslash"),
    pytest.param(r"\/", "/", id="slash"),
    pytest.param(r"\b", "\b", id="backspace"),
    pytest.param(r"\f", "\f", id="form-feed"),
    pytest.param(r"\n", "\n", id="newline"),
    pytest.param(r"\r", "\r", id="return"),
    pytest.param(r"\t", "\t", id="tab"),
]


def _inputs(text):
    encoded = text.encode()
    return text, encoded, bytearray(encoded), memoryview(encoded)


def _assert_values(text, expected):
    for value in _inputs(text):
        assert jsonmodem.loads(value) == expected
        if orjson is not None:
            assert orjson.loads(value) == expected


@pytest.mark.parametrize("spelling,decoded", SIMPLE_ESCAPES)
def test_simple_escape_runs(spelling, decoded):
    for count in [1, 2, 3, 7, 8, 15, 16, 31, 32, 33, 65]:
        _assert_values('"' + spelling * count + '"', decoded * count)


@pytest.mark.parametrize("first,first_value", SIMPLE_ESCAPES)
@pytest.mark.parametrize("second,second_value", SIMPLE_ESCAPES)
def test_every_simple_escape_pair(first, first_value, second, second_value):
    for prefix, suffix in [("", ""), ("x", "y"), ("\u00e9", "\U0001f642")]:
        document = '"' + prefix + first + second + suffix + '"'
        _assert_values(document, prefix + first_value + second_value + suffix)


@pytest.mark.parametrize("spelling,decoded", [
    (r"\u0000\t", "\0\t"),
    (r"\n\u007f", "\n\u007f"),
    (r"\u0080\u07ff\u0800", "\u0080\u07ff\u0800"),
    (r"\uD7FF\uE000\uFFFF", "\ud7ff\ue000\uffff"),
    (r"\uD800\uDC00", "\U00010000"),
    (r"\uDBFF\uDFFF", "\U0010ffff"),
    (r"\uD83D\uDE42\uD83D\uDE42", "\U0001f642\U0001f642"),
    (r"\\\uD83D\uDE42" + r'\"', "\\" + "\U0001f642" + '"'),
    (r"\u005c\u006e", r"\n"),
    (r"\u005cn", r"\n"),
    (r"\u0022\n", '"\n'),
    (
        "\u00e9" + r"\n\t" + "\U0001f642" + r"\u2603\r",
        "\u00e9\n\t\U0001f642\u2603\r",
    ),
    (r"\/\u002f\\", "//\\"),
    (r"\uD83d\uDe42\n\t", "\U0001f642\n\t"),
])
def test_adjacent_unicode_and_simple_escapes(spelling, decoded):
    _assert_values('"' + spelling + '"', decoded)


@pytest.mark.parametrize("length", [
    0, 1, 6, 7, 8, 9, 14, 15, 16, 17, 30, 31, 32, 33,
    46, 47, 48, 49, 62, 63, 64, 65,
])
def test_plain_text_between_escape_runs_at_scanner_boundaries(length):
    plain = "x" * length
    for spelling, decoded in [
        (plain + r"\n\t", plain + "\n\t"),
        (r"\n\t" + plain, "\n\t" + plain),
        (r"\n\t" + plain + r"\r\f", "\n\t" + plain + "\r\f"),
        (
            r"\n" + "\u00e9\U0001f642" + plain + r"\t",
            "\n\u00e9\U0001f642" + plain + "\t",
        ),
    ]:
        _assert_values('"' + spelling + '"', decoded)


@pytest.mark.parametrize("tail,message,position", [
    ("", "unterminated string", 0),
    ("\\", "incomplete escape", 1),
    (r'\q"', "invalid escaped character in string", 1),
    ("\\\u00e9\"", "invalid escaped character in string", 1),
    ("\\\n", "invalid escaped character in string", 1),
    (r'\u"', "invalid escaped sequence in string", 0),
    (r'\u0"', "invalid escaped sequence in string", 0),
    (r'\u00"', "invalid escaped sequence in string", 0),
    (r'\u000"', "invalid escaped sequence in string", 0),
    (r'\u00x0"', "invalid escaped sequence in string", 0),
    (r"\u0000", "unterminated string", 6),
    (r'\uD800"', "no low surrogate in string", 6),
    (r'\uD800\q"', "no low surrogate in string", 6),
    (r"\uD800\u", "invalid escaped sequence in string", 6),
    (r'\uD800\uZZZZ"', "invalid escaped sequence in string", 6),
    (r'\uD800\u0000"', "invalid low surrogate in string", 6),
    (r'\uD800\uD800"', "invalid low surrogate in string", 6),
    (r'\uDC00"', "invalid high surrogate in string", 0),
    (r'\uDFFF"', "invalid high surrogate in string", 0),
    (r'\uD83D\uDE42\q"', "invalid escaped character in string", 13),
    (r"\uD83D\uDE42" + "\\", "incomplete escape", 13),
    (r"\uD83D\uDE42", "unterminated string", 12),
    ("\n\"", "unescaped control character", 0),
    ("\0\"", "unescaped control character", 0),
    (r"\\", "unterminated string", 2),
    (r'\"', "unterminated string", 2),
])
@pytest.mark.parametrize("head", [
    pytest.param(r'"\n\t', id="root"),
    pytest.param('[\n"\u00e9\U0001f642",\n' + r'"\n\t', id="array"),
    pytest.param('{\n"\u00e9\U0001f642":' + r'"\n\t', id="object"),
])
def test_adjacent_escape_errors_preserve_all_fields(head, tail, message, position):
    document = head + tail
    expected = json.JSONDecodeError(message, document, len(head) + position)
    for value in _inputs(document):
        with pytest.raises(jsonmodem.JSONDecodeError) as caught:
            jsonmodem.loads(value)
        error = caught.value
        assert (error.msg, error.pos, error.lineno, error.colno, error.doc, error.args) == (
            expected.msg, expected.pos, expected.lineno, expected.colno,
            expected.doc, expected.args,
        )


@pytest.mark.parametrize("count", [0, 1, 16382, 16384, 16386])
@pytest.mark.parametrize("ensure_ascii", [False, True])
def test_adjacent_escape_values_and_keys_outlive_buffer_reuse(count, ensure_ascii):
    large = '\n\t\\"' * count
    first = "\u00e9\n\t"
    second = '\U0001f642"\\'
    expected = [
        large,
        {large: first, first: second, second: "last\r\f"},
        ["plain", second, first, large],
        {first: large, second: first},
    ]
    document = json.dumps(expected, ensure_ascii=ensure_ascii)
    _assert_values(document, expected)


@pytest.mark.parametrize("count", [1, 1000])
def test_adjacent_escaped_keys_keep_duplicate_semantics(count):
    record = (
        r'{"\n\t":0,"\u000a\u0009":1,"\ud83d\ude42\n":"first",'
        '"\U0001f642\\n":"last"}'
    )
    document = "[" + ",".join([record] * count) + "]"
    _assert_values(document, [{"\n\t": 1, "\U0001f642\n": "last"}] * count)
