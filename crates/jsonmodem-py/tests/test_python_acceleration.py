"""Optional encoding work preserves values, ownership and per-call selection."""

import datetime
import enum
import gc
import json
import os
import sys

import pytest

import jsonmodem
from jsonmodem import _compat, portable


ENCODERS = pytest.mark.parametrize(
    "dumps", [jsonmodem._native.dumps, portable.dumps], ids=["automatic", "portable"]
)


def test_portable_exports_and_build_feature():
    assert portable.__all__ == jsonmodem.__all__
    assert portable.loads is jsonmodem.loads
    assert portable.Fragment is jsonmodem.Fragment
    assert portable.dumps.__name__ == "dumps"
    assert isinstance(jsonmodem._native._has_python_acceleration, bool)
    expected = os.environ.get("JSONMODEM_EXPECT_ACCELERATION")
    if expected is not None:
        assert expected in ("0", "1")
        assert jsonmodem._native._has_python_acceleration == (expected == "1")


@pytest.mark.parametrize("option", [0, jsonmodem.OPT_SORT_KEYS])
def test_portable_does_not_rebuild_unused_key_helpers(monkeypatch, option):
    def unexpected_helpers(_):
        pytest.fail("Non-string key conversion is disabled")

    monkeypatch.setattr(_compat, "_portable_helpers", unexpected_helpers)
    value = datetime.datetime(2024, 1, 2, 3, 4, 5)
    assert portable.dumps(value, option=option) == b'"2024-01-02T03:04:05"'
    assert portable.dumps({"date": value}, option=option) == b'{"date":"2024-01-02T03:04:05"}'


@ENCODERS
@pytest.mark.parametrize("owner_count", [1, 2, 8, 9, 17])
@pytest.mark.parametrize("option", [0, 1, 8, 32, 128, 1024, 1 | 8 | 128 | 1024])
def test_repeated_offsets_and_eviction(dumps, owner_count, option):
    oracle = pytest.importorskip("orjson")
    zones = [
        datetime.timezone(datetime.timedelta(minutes=index - 8), f"zone-{index}")
        for index in range(owner_count)
    ]
    values = [
        datetime.datetime(2024, 2, 29, 3, 4, 5, 123456, zones[index % owner_count])
        for index in range(65)
    ]
    value = {"dates": values, "again": values[0]}
    expected = oracle.dumps(value, option=option)
    result = dumps(value, option=option)
    assert result == expected
    del value, values, zones
    gc.collect()
    assert dumps([datetime.datetime(2001, 1, 1)]) == b'["2001-01-01T00:00:00"]'
    assert result == expected


@ENCODERS
def test_equal_offsets_with_distinct_owners(dumps):
    zones = [datetime.timezone(datetime.timedelta(hours=1), f"name-{i}") for i in range(20)]
    assert all(zones[0] == zone for zone in zones)
    assert all(zones[0] is not zone for zone in zones[1:])
    values = [datetime.datetime(2024, 1, 2, tzinfo=zone) for zone in zones]
    expected = json.dumps(["2024-01-02T00:00:00+01:00"] * len(values), separators=(",", ":")).encode()
    assert dumps(values * 3) == b"[" + b",".join([expected[1:-1]] * 3) + b"]"


@ENCODERS
def test_custom_timezone_is_not_cached(dumps):
    calls = []

    class Timezone(datetime.tzinfo):
        def utcoffset(self, value):
            calls.append(value)
            return datetime.timedelta(minutes=len(calls))

    value = datetime.datetime(2024, 1, 2, tzinfo=Timezone())
    assert dumps([value] * 3) == (
        b'["2024-01-02T00:00:00+00:01","2024-01-02T00:00:00+00:02",'
        b'"2024-01-02T00:00:00+00:03"]'
    )
    assert len(calls) == 3 and all(item is value for item in calls)


@ENCODERS
def test_fixed_timezone_with_offset_subclass_is_not_cached(dumps):
    calls = []

    class Offset(datetime.timedelta):
        @property
        def seconds(self):
            calls.append("seconds")
            return len(calls) * 60

    zone = datetime.timezone(Offset(hours=1))
    value = datetime.datetime(2024, 1, 2, tzinfo=zone)
    calls.clear()
    assert dumps([value] * 3) == (
        b'["2024-01-02T00:00:00+00:01","2024-01-02T00:00:00+00:02",'
        b'"2024-01-02T00:00:00+00:03"]'
    )
    assert calls == ["seconds"] * 3


@ENCODERS
def test_cached_owners_survive_input_mutation_and_reentry(dumps):
    zones = [datetime.timezone(datetime.timedelta(minutes=i + 1)) for i in range(12)]
    values = [datetime.datetime(2024, 1, 2, tzinfo=zone) for zone in zones]
    texts = [value.isoformat() for value in values]
    marker = object()
    parent = [*values, marker, *values]

    def default(value):
        assert value is marker
        parent.clear()
        zones.clear()
        values.clear()
        gc.collect()
        assert jsonmodem._native.dumps(datetime.date(2000, 1, 1)) == b'"2000-01-01"'
        assert portable.dumps(datetime.date(2001, 1, 1)) == b'"2001-01-01"'
        return None

    expected = json.dumps([*texts, None, *texts], separators=(",", ":")).encode()
    assert dumps(parent, default=default) == expected
    assert parent == []


@ENCODERS
@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython reference counts")
def test_error_releases_cached_timezone_owners(dumps):
    zone = datetime.timezone(datetime.timedelta(minutes=1))
    values = [datetime.datetime(2024, 1, 2, tzinfo=zone)] * 16 + [object()]
    references = sys.getrefcount(zone)
    for _ in range(20):
        with pytest.raises(TypeError):
            dumps(values)
        assert sys.getrefcount(zone) == references


class Key(enum.Enum):
    NUMBER = 7


@ENCODERS
@pytest.mark.parametrize("later_zones", [0, 8, 20])
@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython reference-count finalization")
def test_timezone_name_finalizer_is_not_delayed_by_cache(dumps, later_zones):
    released = []

    class Name(str):
        def __del__(self):
            released.append("released")

    first, last = object(), object()
    later = [
        datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone(datetime.timedelta(minutes=i + 2)))
        for i in range(later_zones)
    ]
    expected = ["2024-01-02T00:00:00+01:00", ["released"]]
    expected.extend(value.isoformat() for value in later)
    expected.append(["released"])
    parent = [
        datetime.datetime(
            2024, 1, 2,
            tzinfo=datetime.timezone(datetime.timedelta(hours=1), Name("named")),
        ),
        first, *later, last,
    ]

    def default(value):
        assert value is first or value is last
        parent.clear()
        gc.collect()
        return list(released)

    assert dumps(parent, default=default) == json.dumps(expected, separators=(",", ":")).encode()
    assert released == ["released"]


def test_portable_package_key_helper_uses_portable_encoder(monkeypatch):
    calls = []
    original = jsonmodem._native._dumps_portable

    def capture(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(jsonmodem._native, "_dumps_portable", capture)
    value = {Key.NUMBER: datetime.date(2024, 1, 2)}
    assert portable.dumps(value, option=4) == b'{"7":"2024-01-02"}'
    assert calls == ([7] if jsonmodem._native._has_python_acceleration else [])


@ENCODERS
def test_replaced_key_helper_is_preserved(dumps, monkeypatch):
    calls = []

    def key_text(value, option):
        calls.append((value, option))
        return "replacement"

    helpers = list(_compat._ENCODER_HELPERS)
    helpers[2] = key_text
    monkeypatch.setattr(_compat, "_ENCODER_HELPERS", tuple(helpers))
    assert dumps({Key.NUMBER: datetime.date(2024, 1, 2)}, option=4) == (
        b'{"replacement":"2024-01-02"}'
    )
    assert calls == [(Key.NUMBER, 4)]


@ENCODERS
def test_captured_key_helper_preserves_replaced_recursive_helper(dumps, monkeypatch):
    calls = []

    def replacement(value, option):
        calls.append((value, option))
        return "recursive"

    monkeypatch.setattr(_compat, "key_text", replacement)
    assert dumps({Key.NUMBER: datetime.date(2024, 1, 2)}, option=4) == (
        b'{"recursive":"2024-01-02"}'
    )
    assert calls == [(7, 4)]


@ENCODERS
def test_replaced_primitive_helper_is_preserved(dumps, monkeypatch):
    calls = []

    def replacement(value):
        calls.append(value)
        return b"9"

    monkeypatch.setattr(jsonmodem._native, "dumps", replacement)
    assert dumps({Key.NUMBER: datetime.date(2024, 1, 2)}, option=4) == b'{"9":"2024-01-02"}'
    assert calls == [7]


@ENCODERS
def test_explicit_default_none_and_option_errors_are_preserved(dumps):
    with pytest.raises(TypeError) as caught:
        dumps(object(), default=None)
    assert isinstance(caught.value.__cause__, TypeError)
    with pytest.raises(TypeError, match="unsupported option bits"):
        dumps({}, option=4096)
    with pytest.raises(TypeError, match="option must be an integer"):
        dumps({}, option=True)
