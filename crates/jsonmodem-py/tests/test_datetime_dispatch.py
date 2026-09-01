"""Repeated builtin types must retain the ordinary datetime fallback behavior."""

import datetime
import gc
import json
import sys

import pytest

import jsonmodem
from test_streaming_security import run_python


VALUES = (
    datetime.datetime(2024, 1, 2, 3, 4, 5),
    datetime.date(2024, 1, 2),
    datetime.time(3, 4, 5),
)


@pytest.mark.parametrize("value", VALUES)
def test_replaced_helper_tuple_does_not_change_current_call(value, monkeypatch):
    from jsonmodem import _compat

    helpers = _compat._ENCODER_HELPERS
    replacement = (type(value), *helpers[1:])
    marker = object()
    calls = []

    def default(item):
        assert item is marker
        calls.append(item)
        monkeypatch.setattr(_compat, "_ENCODER_HELPERS", replacement)
        with pytest.raises(AttributeError, match="value"):
            jsonmodem.dumps(value)
        return None

    expected = json.dumps([value.isoformat(), None, value.isoformat()], separators=(",", ":")).encode()
    assert jsonmodem._native._dumps_objects(
        [value, marker, value], default, 0, True, helpers
    ) == expected
    assert calls == [marker]


@pytest.mark.parametrize("index,value", tuple(enumerate(VALUES, start=4)))
def test_removed_datetime_helper_still_selects_default(index, value):
    from jsonmodem import _compat

    helpers = list(_compat._ENCODER_HELPERS)
    helpers[index] = None
    calls = []

    def default(item):
        calls.append(item)
        return "default"

    assert jsonmodem._native._dumps_objects(
        [value, value], default, 0, True, tuple(helpers)
    ) == b'["default","default"]'
    assert calls == [value, value]


@pytest.mark.parametrize("value", VALUES)
def test_enum_helper_alias_keeps_priority_after_another_builtin(value):
    from jsonmodem import _compat

    prefix = datetime.date(2000, 1, 1) if type(value) is datetime.time else datetime.time(1, 2, 3)
    helpers = list(_compat._ENCODER_HELPERS)
    helpers[0] = type(value)
    with pytest.raises(AttributeError, match="value"):
        jsonmodem._native._dumps_objects([prefix, value, value], None, 0, False, tuple(helpers))


@pytest.mark.parametrize("value", VALUES)
@pytest.mark.parametrize("option", [0, 256, 512])
def test_subclasses_and_passthrough_after_a_builtin(value, option):
    class Subclass(type(value)):
        """A Python subclass must continue to reach the supplied default."""

    if type(value) is datetime.time:
        subclass = Subclass(3, 4, 5)
    else:
        subclass = Subclass(2024, 1, 2)
    calls = []

    def default(item):
        calls.append(item)
        return "custom"

    values = [value, subclass, value]
    expected = ["custom"] * 3 if option & 512 else [value.isoformat(), "custom", value.isoformat()]
    assert jsonmodem.dumps(values, default=default, option=option) == json.dumps(
        expected, separators=(",", ":")
    ).encode()
    assert calls == (values if option & 512 else [subclass])


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython pickle-state fields")
@pytest.mark.parametrize("value,state,expected", [
    (VALUES[0], b"\xff\xff\x01\x01\x00\x00\x00\x00\x00\x00", "65535-01-01T00:00:00"),
    (VALUES[1], b"\x00\x00\x01\x01", "0000-01-01"),
    (VALUES[2], b"\x17\xff\xff\xff\xff\xff", "23:255:255.16777215"),
])
def test_pickle_fields_still_fall_back_after_native_success(value, state, expected, monkeypatch):
    from jsonmodem import _compat

    unusual = type(value)(state)
    original = _compat.datetime_text
    calls = []

    def datetime_text(item, option):
        calls.append(item)
        return original(item, option)

    monkeypatch.setattr(_compat, "datetime_text", datetime_text)
    assert jsonmodem.dumps([value, unusual, value]) == json.dumps(
        [value.isoformat(), expected, value.isoformat()], separators=(",", ":")
    ).encode()
    assert sum(item is unusual for item in calls) == 1
    assert all(item is value or item is unusual for item in calls)
    assert len(calls) in (1, 3)


def test_timezone_callback_after_native_success_keeps_ownership_and_reentry():
    parent = []
    calls = []

    class Timezone(datetime.tzinfo):
        """The fallback callback can remove every input-list reference."""

        def utcoffset(self, value):
            calls.append(value)
            parent.clear()
            gc.collect()
            assert jsonmodem.dumps([VALUES[1], VALUES[1]]) == b'["2024-01-02","2024-01-02"]'
            return datetime.timedelta(0)

    ordinary = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
    fallback = ordinary.replace(tzinfo=Timezone())
    parent.extend([ordinary, fallback, ordinary])
    assert jsonmodem.dumps(parent, option=128) == (
        b'["2024-01-02T00:00:00Z","2024-01-02T00:00:00Z","2024-01-02T00:00:00Z"]'
    )
    assert len(calls) == 1 and calls[0] is fallback and parent == []


@pytest.mark.parametrize("attribute", ["days", "seconds"])
def test_offset_subclass_exception_after_native_success(attribute):
    error = RuntimeError("offset field")

    class Offset(datetime.timedelta):
        """Exact timezone objects can still contain a Python timedelta subclass."""

        def __getattribute__(self, name):
            if name == attribute:
                raise error
            return super().__getattribute__(name)

    value = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone(Offset(hours=1)))
    with pytest.raises(RuntimeError) as caught:
        jsonmodem.dumps([VALUES[0], value, VALUES[0]])
    assert caught.value is error
    assert jsonmodem.dumps([VALUES[0], VALUES[0]]) == (
        b'["2024-01-02T03:04:05","2024-01-02T03:04:05"]'
    )


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython datetime C API")
def test_missing_c_api_can_recover_during_one_call():
    result = run_python('''
import datetime
import sys
api = datetime.datetime_CAPI
del datetime.datetime_CAPI
try:
    import jsonmodem
    marker = object()
    value = datetime.date(2024, 1, 2)
    unusual = datetime.date(b"\\x00\\x00\\x01\\x01")
    def default(item):
        assert item is marker
        datetime.datetime_CAPI = api
        return None
    assert jsonmodem.dumps([value, marker, value, unusual], default=default) == (
        b'["2024-01-02",null,"2024-01-02","0000-01-01"]'
    )
    assert "orjson" not in sys.modules
finally:
    datetime.datetime_CAPI = api
''')
    assert result.returncode == 0, result.stdout + result.stderr
