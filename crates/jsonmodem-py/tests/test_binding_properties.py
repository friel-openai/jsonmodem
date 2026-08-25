"""Seeded differential tests exercise the compiled Python binding, not just Rust."""

import json
import math
import random

import pytest

import jsonmodem


def finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite float")
    return value


def tree(rng, depth=0):
    alphabet = 'abcXYZ012\x00\x1f\n\r\t"\\/\u00e9\u2603\U0001f642'
    choices = 5 if depth == 4 else 7
    kind = rng.randrange(choices)
    if kind == 0:
        return None
    if kind == 1:
        return bool(rng.randrange(2))
    if kind == 2:
        return rng.randrange(-(2**63), 2**64)
    if kind == 3:
        return rng.uniform(-1e100, 1e100)
    if kind == 4:
        return ''.join(rng.choices(alphabet, k=rng.randrange(100)))
    if kind == 5:
        return [tree(rng, depth + 1) for _ in range(rng.randrange(5))]
    return {str(index): tree(rng, depth + 1) for index in range(rng.randrange(5))}


def test_generated_documents_and_mutations():
    rng = random.Random(20260825)
    for _ in range(5000):
        value = tree(rng)
        document = json.dumps(value, ensure_ascii=bool(rng.randrange(2))).encode()
        assert jsonmodem.loads(document) == value
        assert json.loads(jsonmodem.dumps(value)) == value
        # Delete or replace bytes around arbitrary token/UTF-8 boundaries.
        position = rng.randrange(len(document))
        mutated = document[:position] + bytes([rng.randrange(256)]) + document[position + 1:]
        try:
            expected = json.loads(mutated.decode('utf-8'), parse_float=finite_float)
            json.dumps(expected, ensure_ascii=False).encode('utf-8')
        except (ValueError, UnicodeError):
            with pytest.raises(jsonmodem.JSONDecodeError):
                jsonmodem.loads(mutated)
        else:
            assert jsonmodem.loads(mutated) == expected


def test_arbitrary_bytes_never_escape_as_panics():
    rng = random.Random(42)
    for _ in range(10000):
        document = bytes(rng.randrange(256) for _ in range(rng.randrange(128)))
        try:
            result = jsonmodem.loads(document)
        except jsonmodem.JSONDecodeError:
            continue
        assert result == json.loads(document)


@pytest.mark.parametrize("option", [0, jsonmodem.OPT_SORT_KEYS])
def test_strict_integer_boundaries(option):
    for value in (-(2**53) + 1, 2**53 - 1):
        assert jsonmodem.dumps({"x": value}, option=option | jsonmodem.OPT_STRICT_INTEGER) == (
            b'{"x":' + str(value).encode() + b'}'
        )


def test_fragment_tampering_and_aggregate_depth():
    fragment = jsonmodem.Fragment(b'0')
    with pytest.raises(AttributeError):
        fragment.value = b'null'
    fragment._value = b'0, "injected":true'
    with pytest.raises(jsonmodem.JSONEncodeError):
        jsonmodem.dumps({"x": fragment})
    fragment = jsonmodem.Fragment(b'[' * 256 + b']' * 256)
    with pytest.raises(jsonmodem.JSONEncodeError):
        jsonmodem.dumps([fragment])


def test_default_mutating_parent_is_a_python_error_not_native_iterator_panic():
    value = {"x": object()}

    def default(_):
        value["new"] = 1
        return None

    with pytest.raises(jsonmodem.JSONEncodeError):
        jsonmodem.dumps(value, default=default)


def test_container_subclass_passthrough():
    class Secret(list):
        pass

    assert jsonmodem.dumps(Secret([1]), default=lambda _: "redacted",
                           option=jsonmodem.OPT_PASSTHROUGH_SUBCLASS) == b'"redacted"'


def test_non_string_key_collisions_are_not_silently_discarded():
    with pytest.raises(jsonmodem.JSONEncodeError, match="collide"):
        jsonmodem.dumps({1: "a", "1": "b"}, option=jsonmodem.OPT_NON_STR_KEYS)


@pytest.mark.parametrize("value", [{}, [], (), {"a": [1, {"b": ()}], "c": [True, None]}])
def test_iterative_serializer_indentation(value):
    expected = json.dumps(value, indent=2, ensure_ascii=False).encode()
    assert jsonmodem.dumps(value, option=jsonmodem.OPT_INDENT_2) == expected


def test_shared_container_is_not_a_cycle():
    item = [1, {"x": 2}]
    assert jsonmodem.loads(jsonmodem.dumps([item, item])) == [item, item]
