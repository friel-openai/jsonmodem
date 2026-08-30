"""Fixed-offset formatting must preserve rounding, callbacks, and ownership."""

import dataclasses
import datetime
import gc
import json
import sys

import pytest

import jsonmodem
from test_datetime_native import OPTIONS
from test_streaming_security import run_python


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("named", [False, True])
@pytest.mark.parametrize("offset_us,suffix", [
    (0, "+00:00"),
    (1, "+00:00"),
    (-1, "-00:00"),
    (29_000_000, "+00:00"),
    (29_999_999, "+00:00"),
    (-29_000_000, "-00:00"),
    (-29_000_001, "-00:01"),
    (30_000_000, "+00:01"),
    (-30_000_000, "-00:01"),
    (31_000_000, "+00:01"),
    (-31_000_000, "-00:01"),
    (59_999_999, "+00:01"),
    (-59_999_999, "-00:01"),
    (3_600_000_000, "+01:00"),
    (-3_600_000_000, "-01:00"),
    (19_800_000_000, "+05:30"),
    (-12_600_000_000, "-03:30"),
    (86_369_000_000, "+23:59"),
    (-86_369_000_000, "-23:59"),
    (86_370_000_000, "+24:00"),
    (-86_370_000_000, "-24:00"),
    (86_399_999_999, "+24:00"),
    (-86_399_999_999, "-24:00"),
])
def test_fixed_offset_rounding(offset_us, suffix, named, option):
    offset = datetime.timedelta(microseconds=offset_us)
    timezone = (datetime.timezone(offset, "fixed") if named
                else datetime.timezone(offset))
    value = datetime.datetime(2024, 2, 29, 3, 4, 5, 40974, timezone, fold=1)
    if option & 128 and suffix in ("+00:00", "-00:00"):
        suffix = "Z"
    fraction = "" if option & 8 else ".040974"
    expected = f'"2024-02-29T03:04:05{fraction}{suffix}"'.encode()
    assert jsonmodem.dumps(value, option=option) == expected
    assert jsonmodem.dumps([value], option=option) == b"[" + expected + b"]"


@pytest.mark.parametrize("option", OPTIONS)
@pytest.mark.parametrize("minutes", [-1439, -210, 0, 330, 1439])
@pytest.mark.parametrize("microsecond", [0, 999999])
def test_minute_offsets_match_reference(minutes, microsecond, option):
    timezone = datetime.timezone(datetime.timedelta(minutes=minutes), "fixed")
    value = datetime.datetime(1, 2, 3, 4, 5, 6, microsecond, timezone)
    oracle = pytest.importorskip("orjson")
    assert jsonmodem.dumps(value, option=option) == oracle.dumps(value, option=option)


@pytest.mark.parametrize("option", [0, 1, 32, 1024, 1 | 32 | 1024, 2 | 8 | 128])
def test_fixed_offsets_in_containers(option):
    @dataclasses.dataclass
    class Record:
        value: object

    timezone = datetime.timezone(datetime.timedelta(hours=-3, minutes=-30))
    value = datetime.datetime(9999, 12, 31, 23, 59, 59, 123456, timezone)
    text = "9999-12-31T23:59:59" + ("" if option & 8 else ".123456") + "-03:30"
    expected = json.dumps(
        {"z": [text, text], "a": {"value": text}},
        indent=2 if option & 1 else None,
        separators=(",", ": ") if option & 1 else (",", ":"),
        sort_keys=bool(option & 32),
    ).encode()
    if option & 1024:
        expected += b"\n"
    assert jsonmodem.dumps({"z": (value, value), "a": Record(value)}, option=option) == expected


@pytest.mark.parametrize("option", OPTIONS)
def test_timedelta_subclass_fields_keep_python_behavior(option):
    class Offset(datetime.timedelta):
        """The stored offset is valid, but Python attributes change formatting."""

        @property
        def days(self):
            return 2

        @property
        def seconds(self):
            return 3661

    timezone = datetime.timezone(Offset(hours=1))
    value = datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone)
    assert jsonmodem.dumps(value, option=option) == b'"2024-01-02T03:04:05+49:01"'


@pytest.mark.parametrize("attribute", ["days", "seconds"])
def test_timedelta_subclass_exception_is_preserved(attribute):
    error = RuntimeError("offset attribute")

    class Offset(datetime.timedelta):
        """Attribute access fails after the builtin timezone returns its offset."""

        def __getattribute__(self, name):
            if name == attribute:
                raise error
            return super().__getattribute__(name)

    value = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone(Offset(hours=1)))
    with pytest.raises(RuntimeError) as caught:
        jsonmodem.dumps(value)
    assert caught.value is error


def test_timedelta_subclass_can_mutate_parent_and_reenter():
    parent = []
    calls = []

    class Offset(datetime.timedelta):
        """A Python field getter can run arbitrary code while formatting."""

        @property
        def days(self):
            calls.append("days")
            parent.clear()
            gc.collect()
            assert jsonmodem.dumps(datetime.date(2024, 1, 2)) == b'"2024-01-02"'
            return 0

    timezone = datetime.timezone(Offset(hours=1))
    parent.extend([datetime.datetime(2024, 1, 2, tzinfo=timezone), datetime.date(9999, 12, 31)])
    assert jsonmodem.dumps(parent) == b'["2024-01-02T00:00:00+01:00","9999-12-31"]'
    assert calls == ["days"] and parent == []


@pytest.mark.parametrize("option", OPTIONS)
def test_fixed_offset_passthrough_does_not_read_offset(option):
    class Offset(datetime.timedelta):
        """Passthrough must avoid formatting this offset's fields."""

        @property
        def days(self):
            raise AssertionError("offset must not be formatted")

    value = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone(Offset(hours=1)))
    calls = []

    def default(item):
        calls.append(item)
        return "custom"

    assert jsonmodem.dumps(value, option=option | 512, default=default) == b'"custom"'
    assert len(calls) == 1 and calls[0] is value


@pytest.mark.parametrize("option", OPTIONS)
def test_aware_fixed_offset_time_still_raises(option):
    value = datetime.time(1, 2, 3, tzinfo=datetime.timezone(datetime.timedelta(hours=1)))
    with pytest.raises(TypeError, match="timezone library is not supported"):
        jsonmodem.dumps(value, option=option)


def test_fixed_offset_dictionary_keys_keep_existing_conversion():
    timezone = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    value = datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone)
    assert jsonmodem.dumps({value: value}, option=4) == (
        b'{"2024-01-02T03:04:05+05:30":"2024-01-02T03:04:05+05:30"}'
    )


@pytest.mark.skipif(
    sys.implementation.name != "cpython" or not getattr(sys, "_is_gil_enabled", lambda: True)(),
    reason="checks GIL-enabled CPython reference counts and finalization order",
)
def test_ephemeral_timezone_is_released_before_next_default():
    calls = []
    first, second = object(), object()

    class Name(str):
        """A name's finalizer makes a timezone's extended lifetime observable."""

        def __del__(self):
            calls.append("name released")

    def default(value):
        if value is first:
            return datetime.datetime(
                2024, 1, 2,
                tzinfo=datetime.timezone(datetime.timedelta(hours=1), Name("temporary")),
            )
        assert value is second
        assert calls == ["name released"]
        return 0

    assert jsonmodem.dumps([first, second], default=default) == b'["2024-01-02T00:00:00+01:00",0]'
    assert calls == ["name released"]


@pytest.mark.skipif(
    sys.implementation.name != "cpython" or not getattr(sys, "_is_gil_enabled", lambda: True)(),
    reason="checks GIL-enabled CPython reference counts",
)
def test_fixed_offset_owners_are_released_after_each_call():
    offset = datetime.timedelta(hours=5, minutes=30)
    timezone = datetime.timezone(offset, "fixed")
    value = datetime.datetime(2024, 1, 2, tzinfo=timezone)
    jsonmodem.dumps([value])
    before = [sys.getrefcount(item) for item in (offset, timezone, value)]
    for _ in range(100):
        jsonmodem.dumps([value])
    gc.collect()
    assert [sys.getrefcount(item) for item in (offset, timezone, value)] == before


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython pickle-state fields")
@pytest.mark.parametrize("state,expected", [
    (b"\xff\xff\x01\x01\x00\x00\x00\x00\x00\x00", "65535-01-01T00:00:00+01:00"),
    (b"\x07\xe8\x01\xff\xff\xff\xff\xff\xff\xff", "2024-01-255T255:255:255.16777215+01:00"),
])
def test_pickle_state_fixed_offset_keeps_fallback(state, expected):
    value = datetime.datetime(state, datetime.timezone(datetime.timedelta(hours=1)))
    assert jsonmodem.dumps(value) == json.dumps(expected).encode()


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython datetime C API")
def test_missing_datetime_c_api_keeps_fixed_offset_fallback():
    result = run_python('''
import datetime
import sys
api = datetime.datetime_CAPI
del datetime.datetime_CAPI
try:
    import jsonmodem
    value = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone(datetime.timedelta(hours=1)))
    assert "orjson" not in sys.modules
    assert jsonmodem.dumps(value) == b'"2024-01-02T00:00:00+01:00"'
finally:
    datetime.datetime_CAPI = api
assert jsonmodem.dumps(value) == b'"2024-01-02T00:00:00+01:00"'
''')
    assert result.returncode == 0, result.stdout + result.stderr
