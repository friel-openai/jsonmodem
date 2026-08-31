"""UUID formatting, mutable attributes, and ownership during callbacks."""

import dataclasses
import datetime
import enum
import gc
import json
import uuid

import pytest

import jsonmodem
from test_streaming_security import run_python


def uuid_text(number):
    digits = f"{int.__int__(number):032x}"
    return "-".join((digits[:8], digits[8:12], digits[12:16], digits[16:20], digits[20:]))


def uuid_bytes(number):
    return b'"' + uuid_text(number).encode("ascii") + b'"'


class StoredInt(int):
    def __int__(self):
        raise AssertionError("integer override called")

    def __index__(self):
        raise AssertionError("index override called")

    def __format__(self, spec):
        raise AssertionError("format override called")

    def __rshift__(self, count):
        raise AssertionError("shift override called")


class IntegerCode(enum.IntEnum):
    VALUE = 42


@dataclasses.dataclass
class Record:
    value: object


class TestUUIDOrdinary:
    @pytest.mark.parametrize("number", [
        0, 1, 15, 16, 255, 256,
        (1 << 32) - 1, 1 << 32, (1 << 48) - 1, 1 << 48,
        (1 << 64) - 1, 1 << 64, (1 << 96) - 1, 1 << 96,
        (1 << 127) - 1, 1 << 127, (1 << 128) - 1,
        0x0123456789ABCDEF0123456789ABCDEF,
        0xFEDCBA9876543210FEDCBA9876543210,
        *[1 << shift for shift in range(0, 128, 4)],
    ])
    def test_integer_boundaries(self, number):
        assert jsonmodem.dumps(uuid.UUID(int=number)) == uuid_bytes(number)

    @pytest.mark.parametrize("kind", ["hex", "bytes", "bytes_le", "fields"])
    def test_constructor_forms(self, kind):
        value = uuid.UUID("12345678-1234-5678-9abc-def012345678")
        argument = str(value) if kind == "hex" else getattr(value, kind)
        assert jsonmodem.dumps(uuid.UUID(**{kind: argument})) == uuid_bytes(value.int)

    @pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("is_safe", list(uuid.SafeUUID))
    def test_version_and_safety_metadata(self, version, is_safe):
        value = uuid.UUID(int=(1 << 128) - 1, version=version, is_safe=is_safe)
        assert jsonmodem.dumps(value) == uuid_bytes(value.int)

    @pytest.mark.parametrize("number", [False, True, StoredInt(0), StoredInt(42),
                                        StoredInt((1 << 128) - 1), IntegerCode.VALUE])
    def test_integer_subclass_storage(self, number):
        value = uuid.UUID(int=number)
        assert value.int is number
        assert jsonmodem.dumps(value) == uuid_bytes(number)

    @pytest.mark.parametrize("context", ["root", "list", "tuple", "dict", "record", "enum", "default"])
    @pytest.mark.parametrize("option", [0, 1, 16, 32, 64, 256, 512, 1024, 1057])
    def test_contexts_and_options(self, context, option):
        value = uuid.UUID(int=(1 << 127) + 123456789)
        expected = uuid_text(value.int)
        calls = []
        if context == "list":
            value, expected = [value, None], [expected, None]
        elif context == "tuple":
            value, expected = (value, True), [expected, True]
        elif context == "dict":
            value, expected = {"z": value, "a": 1}, {"z": expected, "a": 1}
        elif context == "record":
            value, expected = Record(value), {"value": expected}
        elif context == "enum":
            value = enum.Enum("Wrapped", {"VALUE": value}).VALUE
        replacement = value
        if context == "default":
            value = object()

        def default(item):
            calls.append(item)
            assert item is value
            return replacement

        encoded = json.dumps(expected, ensure_ascii=False,
                             indent=2 if option & 1 else None,
                             separators=None if option & 1 else (",", ":"),
                             sort_keys=bool(option & 32)).encode()
        if option & 1024:
            encoded += b"\n"
        assert jsonmodem.dumps(value, default=default, option=option) == encoded
        assert calls == ([value] if context == "default" else [])

    @pytest.mark.parametrize("option", [0, 256, 2048])
    def test_uuid_subclass_uses_default(self, option):
        class Child(uuid.UUID):
            pass

        value = Child(int=42)
        with pytest.raises(TypeError, match="not JSON serializable"):
            jsonmodem.dumps(value, option=option)
        calls = []

        def default(item):
            calls.append(item)
            return "subclass"

        assert jsonmodem.dumps(value, default=default, option=option) == b'"subclass"'
        assert calls == [value]

    def test_uuid_type_is_not_a_uuid_value(self):
        with pytest.raises(TypeError, match="not JSON serializable"):
            jsonmodem.dumps(uuid.UUID)
        assert jsonmodem.dumps(uuid.UUID, default=lambda _: "type") == b'"type"'

    def test_passthrough_dataclass_default_returns_uuid(self):
        value = uuid.UUID(int=(1 << 128) - 1)
        calls = []
        record = Record(value)

        def default(item):
            calls.append(item)
            return item.value

        assert jsonmodem.dumps(record, default=default, option=2048 | 64) == uuid_bytes(value.int)
        assert calls == [record]

    def test_uuid_ignores_dataclass_marker(self, monkeypatch):
        value = uuid.UUID(int=42)
        monkeypatch.setattr(uuid.UUID, "__dataclass_fields__", {}, raising=False)
        assert jsonmodem.dumps(value) == uuid_bytes(42)

    @pytest.mark.parametrize("option", [4, 4 | 32])
    def test_uuid_keys_and_converted_key_collisions(self, option):
        value = uuid.UUID(int=42)
        text = uuid_text(42)
        expected = b"{" + uuid_bytes(42) + b":1," + uuid_bytes(42) + b":2}"
        assert jsonmodem.dumps({value: 1, text: 2}, option=option) == expected
        with pytest.raises(TypeError, match="Dict key must be str"):
            jsonmodem.dumps({value: 1})

    def test_uuid_keys_keep_existing_text_helper(self, monkeypatch):
        value = uuid.UUID(int=42)
        monkeypatch.setattr(uuid.UUID, "__str__", lambda _: "key")
        assert jsonmodem.dumps({value: 1}, option=4) == b'{"key":1}'

    @pytest.mark.parametrize("access", ["descriptor", "getattribute"])
    def test_int_attribute_read_once(self, access, monkeypatch):
        value = uuid.UUID(int=42)
        calls = []
        if access == "descriptor":
            def read(item):
                calls.append(item)
                return 42
            monkeypatch.setattr(uuid.UUID, "int", property(read))
        else:
            def read(item, name):
                if name == "int":
                    calls.append(item)
                return object.__getattribute__(item, name)
            monkeypatch.setattr(uuid.UUID, "__getattribute__", read)
        assert jsonmodem.dumps(value) == uuid_bytes(42)
        assert len(calls) == 1 and calls[0] is value

    @pytest.mark.parametrize("error_type", [AttributeError, TypeError, ValueError, OverflowError, MemoryError])
    def test_getter_exception_is_preserved(self, error_type, monkeypatch):
        value = uuid.UUID(int=42)
        cause = RuntimeError("original cause")
        error = error_type("getter failed")
        error.__cause__ = cause
        calls = []

        def read(item):
            calls.append(item)
            raise error

        def default(_):
            raise AssertionError("default called after UUID getter failed")

        monkeypatch.setattr(uuid.UUID, "int", property(read))
        with pytest.raises(error_type) as raised:
            jsonmodem.dumps(value, default=default)
        assert raised.value is error
        assert raised.value.__cause__ is cause
        assert len(calls) == 1 and calls[0] is value

    def test_missing_int_preserves_attribute_error(self):
        value = uuid.UUID(int=42)
        object.__delattr__(value, "int")
        with pytest.raises(AttributeError, match="int"):
            jsonmodem.dumps(value)
        assert jsonmodem.dumps(uuid.UUID(int=1)) == uuid_bytes(1)

    def test_cycles_and_depth_are_still_checked(self):
        value = uuid.UUID(int=42)
        cycle = [value]
        cycle.append(cycle)
        with pytest.raises(TypeError):
            jsonmodem.dumps(cycle)
        nested = value
        for _ in range(254):
            nested = [nested]
        assert jsonmodem.dumps(nested) == b"[" * 254 + uuid_bytes(42) + b"]" * 254
        with pytest.raises(TypeError):
            jsonmodem.dumps([nested])

    @pytest.mark.parametrize("container", ["list", "dict"])
    def test_getter_retains_pending_items_during_mutation(self, container):
        result = run_python(f'''
import gc, resource, uuid, weakref
import jsonmodem
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
class Pending:
    pass
value = uuid.UUID(int=42)
pending = Pending()
reference = weakref.ref(pending)
source = [value, pending] if {container!r} == "list" else {{"first": value, "next": pending}}
del pending
calls = []
def read(item):
    calls.append(item)
    source.clear()
    gc.collect()
    assert reference() is not None
    assert jsonmodem.dumps([1, "nested"]) == b'[1,"nested"]'
    return 42
uuid.UUID.int = property(read)
def default(item):
    assert item is reference()
    return "retained"
result = jsonmodem.dumps(source, default=default)
expected = b'["00000000-0000-0000-0000-00000000002a","retained"]' if {container!r} == "list" else b'{{"first":"00000000-0000-0000-0000-00000000002a","next":"retained"}}'
assert result == expected
assert len(calls) == 1 and calls[0] is value
gc.collect()
assert reference() is None
''')
        assert result.returncode == 0, result.stdout + result.stderr

    def test_next_uuid_observes_descriptor_change(self, monkeypatch):
        values = [uuid.UUID(int=1), uuid.UUID(int=2)]
        calls = []

        def second(item):
            calls.append(item)
            return 2

        def first(item):
            calls.append(item)
            monkeypatch.setattr(uuid.UUID, "int", property(second))
            return 1

        monkeypatch.setattr(uuid.UUID, "int", property(first))
        assert jsonmodem.dumps(values) == b"[" + uuid_bytes(1) + b"," + uuid_bytes(2) + b"]"
        assert len(calls) == 2 and all(left is right for left, right in zip(calls, values))

    def test_temporary_integer_owner_is_released(self, monkeypatch):
        value = uuid.UUID(int=42)
        released = []

        class Temporary(int):
            def __del__(self):
                released.append(int.__int__(self))
                assert jsonmodem.dumps([1, "nested"]) == b'[1,"nested"]'

        monkeypatch.setattr(uuid.UUID, "int", property(lambda _: Temporary(42)))
        assert jsonmodem.dumps(value) == uuid_bytes(42)
        gc.collect()
        assert released == [42]

    @pytest.mark.parametrize("helper_index", [4, 5, 6])
    def test_datetime_helper_alias_keeps_python_fallback(self, helper_index, monkeypatch):
        from jsonmodem import _compat

        value = uuid.UUID(int=42)
        helpers = list(_compat._ENCODER_HELPERS)
        helpers[helper_index] = uuid.UUID
        monkeypatch.setattr(uuid.UUID, "__str__", lambda _: "datetime fallback")
        assert jsonmodem._native._dumps_objects(
            value, None, 0, False, tuple(helpers)
        ) == b'"datetime fallback"'

    def test_enum_helper_precedes_uuid_formatting(self, monkeypatch):
        from jsonmodem import _compat

        value = uuid.UUID(int=42)
        helpers = list(_compat._ENCODER_HELPERS)
        helpers[0] = uuid.UUID
        monkeypatch.setattr(uuid.UUID, "value", property(lambda _: "enum value"), raising=False)
        assert jsonmodem._native._dumps_objects(
            value, None, 0, False, tuple(helpers)
        ) == b'"enum value"'

    @pytest.mark.parametrize(
        "value",
        [datetime.date(2020, 1, 2), datetime.datetime(2020, 1, 2, 3, 4, 5), datetime.time(3, 4, 5)],
    )
    @pytest.mark.parametrize("option", [0, 512])
    def test_uuid_helper_alias_preserves_date_writer_and_fallback(self, value, option):
        from jsonmodem import _compat

        helpers = list(_compat._ENCODER_HELPERS)
        helpers[7] = type(value)
        calls = []

        def default(item):
            calls.append(item)
            return "passthrough"

        expected = "passthrough" if option else value.isoformat()
        assert jsonmodem._native._dumps_objects(
            value, default, option, True, tuple(helpers)
        ) == json.dumps(expected).encode()
        assert calls == ([value] if option else [])


class TestUUIDNativeBehavior:
    @pytest.mark.parametrize("kind", ["text", "nonstring", "error", "code"])
    def test_str_override_is_ignored(self, kind, monkeypatch):
        value = uuid.UUID(int=42)
        calls = []

        def replacement(item):
            calls.append(item)
            if kind == "error":
                raise RuntimeError("str override called")
            return 1 if kind == "nonstring" else "changed"

        if kind == "code":
            def changed(self):
                return "changed"
            monkeypatch.setattr(uuid.UUID.__str__, "__code__", changed.__code__)
        else:
            monkeypatch.setattr(uuid.UUID, "__str__", replacement)
        assert jsonmodem.dumps(value) == uuid_bytes(42)
        assert calls == []

    def test_initialized_uuid_type_survives_module_rebinding(self, monkeypatch):
        value = uuid.UUID(int=42)
        assert jsonmodem.dumps(value) == uuid_bytes(42)

        class Replacement:
            pass

        monkeypatch.setattr(uuid, "UUID", Replacement)

        def default(_):
            raise AssertionError("UUID sent to default after module rebinding")

        assert jsonmodem.dumps(value, default=default) == uuid_bytes(42)

    @pytest.mark.parametrize("stored", [None, "42", 42.0, [], object()])
    def test_noninteger_state_is_rejected(self, stored):
        value = uuid.UUID(int=42)
        object.__setattr__(value, "int", stored)
        with pytest.raises(TypeError, match="^UUID.int must be an integer$"):
            jsonmodem.dumps(value)
        assert jsonmodem.dumps(uuid.UUID(int=1)) == uuid_bytes(1)

    def test_noninteger_index_is_not_called(self):
        calls = []

        class Index:
            def __index__(self):
                calls.append(self)
                return 42

        value = uuid.UUID(int=42)
        object.__setattr__(value, "int", Index())
        with pytest.raises(TypeError, match="^UUID.int must be an integer$"):
            jsonmodem.dumps(value)
        assert calls == []

    @pytest.mark.parametrize("stored", [-1, -(1 << 128), 1 << 128, 1 << 1024,
                                        StoredInt(-1), StoredInt(1 << 128)])
    def test_out_of_range_state_is_rejected(self, stored):
        value = uuid.UUID(int=42)
        object.__setattr__(value, "int", stored)
        with pytest.raises(TypeError, match="^UUID.int is outside 128-bit range$"):
            jsonmodem.dumps(value)
        assert jsonmodem.dumps(uuid.UUID(int=1)) == uuid_bytes(1)
