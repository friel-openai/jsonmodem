"""Dataclass output and ownership during field access and default callbacks."""

import dataclasses
import gc
import json
import random
import sys
from typing import ClassVar
import weakref

import pytest

import jsonmodem
from test_streaming_security import run_python

@pytest.fixture
def oracle():
    return pytest.importorskip("orjson")


@dataclasses.dataclass
class Record:
    z: object
    a: object
    _private: int = 9


@dataclasses.dataclass
class SlotsRecord:
    __slots__ = ("z", "a", "_private")

    z: object
    a: object
    _private: int
    temporary: dataclasses.InitVar[int] = 0
    shared: ClassVar[str] = "class value"


@pytest.mark.parametrize("option", [0, 1, 32, 33, 64, 256, 1024, 1057, 2048])
@pytest.mark.parametrize("slotted", [False, True])
def test_dataclass_nested_output_and_options(option, slotted, oracle):
    constructor = SlotsRecord if slotted else Record
    child = constructor(3, {"z": 2, "a": 1}, 9)
    value = [constructor(child, [True, None, "quote\"\\\n"], 8), child]
    if not slotted:
        child.extra = "extra field"
        child._extra = "private field"
    default = lambda obj: {"replacement": obj.a}
    assert jsonmodem.dumps(value, option=option, default=default) == oracle.dumps(
        value, option=option, default=default
    )


def test_inherited_slots_use_child_instance_attributes(oracle):
    @dataclasses.dataclass
    class Child(SlotsRecord):
        b: str = "child"

    value = Child(1, 2, 9)
    value.extra = "not a declared field"
    assert jsonmodem.dumps(value) == oracle.dumps(value)


def test_undecorated_subclass_is_not_a_dataclass(oracle):
    class Child(Record):
        pass

    value = Child(1, 2)
    default = lambda _: "converted"
    assert jsonmodem.dumps(value, default=default) == oracle.dumps(value, default=default)


@pytest.mark.parametrize("slotted", [False, True])
def test_dataclass_callback_retains_later_fields(slotted):
    constructor = SlotsRecord if slotted else Record
    original = object()
    later = object()
    value = constructor(original, later, 9)
    calls = []

    def default(item):
        calls.append(item)
        if item is original:
            value.a = "changed during callback"
            if not slotted:
                value.__dict__.clear()
            return "first"
        assert item is later
        return "second"

    assert jsonmodem.dumps(value, default=default) == b'{"z":"first","a":"second"}'
    assert calls == [original, later]


def test_field_getters_are_not_replayed_and_parent_items_are_owned():
    calls = []
    parent = []

    @dataclasses.dataclass
    class GetterRecord:
        __slots__ = ("first", "second")

        first: object
        second: object

        def __getattribute__(self, name):
            if name in ("first", "second"):
                calls.append("get " + name)
                parent.clear()
            return object.__getattribute__(self, name)

    first, second, tail = object(), object(), object()
    parent.extend([GetterRecord(first, second), tail])

    def default(item):
        index = [first, second, tail].index(item)
        calls.append("default " + str(index))
        return index

    assert jsonmodem.dumps(parent, default=default) == b'[{"first":0,"second":1},2]'
    assert calls == ["get first", "get second", "default 0", "default 1", "default 2"]
    assert parent == []


def test_field_getter_cannot_invalidate_parent_dict_iterator():
    parent = {}

    @dataclasses.dataclass
    class GetterRecord:
        __slots__ = ("value",)

        value: int

        def __getattribute__(self, name):
            if name == "value":
                parent.clear()
            return object.__getattribute__(self, name)

    parent.update(first=GetterRecord(1), second=2)
    assert jsonmodem.dumps(parent) == b'{"first":{"value":1},"second":2}'


def test_callback_changes_later_dataclass_metadata():
    @dataclasses.dataclass
    class MutableRecord:
        value: int

    first = object()
    record = MutableRecord(3)
    value = [first, record]
    calls = []

    def default(item):
        calls.append(item)
        if item is first:
            del MutableRecord.__dataclass_fields__
            return 1
        assert item is record
        return "converted"

    assert jsonmodem.dumps(value, default=default) == b'[1,"converted"]'
    assert calls == [first, record]


def test_callback_adds_slots_after_class_dictionary_was_cached():
    @dataclasses.dataclass
    class MutableRecord:
        value: object

    trigger = object()
    first = MutableRecord(trigger)
    second = MutableRecord(2)
    first.extra = "first extra"
    second.extra = "second extra"

    def default(item):
        assert item is trigger
        MutableRecord.__slots__ = ()
        return 1

    assert jsonmodem.dumps([first, second], default=default) == (
        b'[{"value":1,"extra":"first extra"},{"value":2}]'
    )


def test_callback_removes_marker_after_class_dictionary_was_cached():
    @dataclasses.dataclass
    class MutableRecord:
        value: object

    trigger = object()
    first = MutableRecord(trigger)
    second = MutableRecord(2)

    def default(item):
        if item is trigger:
            del MutableRecord.__dataclass_fields__
            return 1
        assert item is second
        return 2

    assert jsonmodem.dumps([first, second], default=default) == b'[{"value":1},2]'


def test_metadata_lookup_does_not_invoke_metaclass_getattribute():
    calls = []

    class Meta(type):
        def __getattribute__(cls, name):
            if name in ("__dict__", "__dataclass_fields__", "__slots__"):
                calls.append(name)
            return type.__getattribute__(cls, name)

    @dataclasses.dataclass
    class MetaRecord(metaclass=Meta):
        value: int

    value = MetaRecord(1)
    calls.clear()
    assert jsonmodem.dumps([value, value]) == b'[{"value":1},{"value":1}]'
    assert calls == []


def test_actual_class_determines_enum_conversion():
    import enum

    @dataclasses.dataclass
    class SpoofedClass:
        value: int

        @property
        def __class__(self):
            raise AssertionError("serialization must use the actual type")

    assert jsonmodem.dumps(SpoofedClass(1)) == b'{"value":1}'

    class Choice(enum.Enum):
        VALUE = Record(2, None)

    assert jsonmodem.dumps(Choice.VALUE) == b'{"z":2,"a":null}'


def test_dataclass_dictionary_is_obtained_once():
    calls = []

    @dataclasses.dataclass
    class GetterRecord:
        value: int

        def __getattribute__(self, name):
            if name == "__dict__":
                calls.append(name)
            return object.__getattribute__(self, name)

    assert jsonmodem.dumps(GetterRecord(1)) == b'{"value":1}'
    assert calls == ["__dict__"]


def test_cached_class_owner_survives_parent_mutation():
    def make_record():
        record_type = dataclasses.make_dataclass("TemporaryRecord", [("value", int)])
        return record_type(1), weakref.ref(record_type)

    record, reference = make_record()
    parent = [record, object()]
    del record

    def default(_):
        parent.clear()
        gc.collect()
        assert reference() is not None
        return None

    assert jsonmodem.dumps(parent, default=default) == b'[{"value":1},null]'
    gc.collect()
    assert reference() is None


def test_field_owner_survives_until_its_default_callback():
    calls = []

    class Later:
        def __del__(self):
            calls.append("released")

    first = object()
    value = Record(first, Later())

    def default(item):
        if item is first:
            value.__dict__.clear()
            gc.collect()
            assert calls == []
            return 1
        assert isinstance(item, Later)
        calls.append("serialized")
        return 2

    assert jsonmodem.dumps(value, default=default) == b'{"z":1,"a":2}'
    assert calls == ["serialized", "released"]


def test_native_output_key_ranges_are_cleared_before_callback_traversal():
    prefix = [{"id": i, "name": "x" * 300} for i in range(20)]
    value = prefix + [Record(1, 2), {"id": 3}]
    expected = prefix + [{"z": 1, "a": 2}, {"id": 3}]
    assert jsonmodem.dumps(value) == json.dumps(expected, separators=(",", ":")).encode()


def test_default_can_return_a_dataclass_and_reenter_encoder():
    first, second = object(), object()
    calls = []

    def default(value):
        calls.append(value)
        if value is first:
            return Record(second, [1, 2])
        assert value is second
        return jsonmodem.Fragment(jsonmodem.dumps(Record(3, 4)))

    assert jsonmodem.dumps([first], default=default) == b'[{"z":{"z":3,"a":4},"a":[1,2]}]'
    assert calls == [first, second]


@pytest.mark.parametrize("slotted", [False, True])
def test_dataclass_cycles_and_shared_instances(slotted):
    constructor = SlotsRecord if slotted else Record
    value = constructor(1, [], 9)
    assert jsonmodem.dumps([value, value]) == b'[{"z":1,"a":[]},{"z":1,"a":[]}]'
    value.a.append(value)
    with pytest.raises(TypeError, match="Recursion"):
        jsonmodem.dumps(value)


@pytest.mark.parametrize("option", [0, 1, 32, 33])
def test_dataclass_and_builtin_depth_share_one_counter(option):
    value = Record(0, None)
    for _ in range(127):
        value = Record([value], None)
    assert jsonmodem.dumps(value, option=option)
    value = Record([value], None)
    with pytest.raises(TypeError, match="Recursion"):
        jsonmodem.dumps(value, option=option)


def test_empty_list_subclass_does_not_count_toward_depth_limit():
    class EmptyList(list):
        def __len__(self):
            raise AssertionError("use the builtin list length")

        def __bool__(self):
            raise AssertionError("do not invoke a list subclass's truthiness")

    value = EmptyList()
    for _ in range(254):
        value = [value]
    assert jsonmodem.dumps(value) == b"[" * 255 + b"]" * 255
    assert jsonmodem.dumps(
        value, default=lambda _: None, option=jsonmodem.OPT_PASSTHROUGH_SUBCLASS
    ) == b"[" * 254 + b"null" + b"]" * 254


def test_empty_list_subclass_depth_matches_orjson(oracle):
    class EmptyList(list):
        pass

    value = EmptyList()
    for _ in range(254):
        value = [value]
    assert jsonmodem.dumps(value) == oracle.dumps(value)


def default_container_chain(module, limit, siblings=1, kind="dataclass", ancestor=0):
    """Alternate callbacks and containers without approaching the container limit."""
    calls = 0

    class Unsupported:
        def __init__(self, step, parent=False):
            self.step = step
            self.parent = parent

    @dataclasses.dataclass
    class Box:
        value: object

    def default(value):
        nonlocal calls
        calls += 1
        step = value.step + 1
        if value.parent:
            if step == ancestor:
                return [Unsupported(0) for _ in range(siblings)]
            return Unsupported(step, parent=True)
        if step == limit:
            return 0
        next_value = Unsupported(step)
        if step % 2:
            return next_value
        if kind == "list":
            return [next_value]
        if kind == "dict":
            return {"value": next_value}
        return Box(next_value)

    value = Unsupported(0, parent=True) if ancestor else [Unsupported(0) for _ in range(siblings)]
    try:
        result = module.dumps(value, default=default)
    except TypeError as error:
        return str(error), calls
    return result, calls


@pytest.mark.parametrize("kind", ["dataclass", "list", "dict"])
def test_default_counter_is_inherited_by_container_children(kind):
    result, calls = default_container_chain(jsonmodem, 255, kind=kind)
    assert isinstance(result, bytes)
    assert calls == 255
    result, calls = default_container_chain(jsonmodem, 256, kind=kind)
    assert result == "default serializer exceeds recursion limit"
    assert calls == 255


@pytest.mark.parametrize("kind", ["dataclass", "list", "dict"])
def test_default_counter_is_restored_for_siblings(kind):
    result, calls = default_container_chain(jsonmodem, 255, siblings=2, kind=kind)
    assert isinstance(result, bytes)
    assert calls == 510


@pytest.mark.parametrize("ancestor,limit", [(100, 155), (100, 156), (254, 1), (255, 1)])
def test_default_counter_restores_nonzero_parent_count(ancestor, limit):
    result, calls = default_container_chain(jsonmodem, limit, siblings=2, ancestor=ancestor)
    if ancestor + limit <= 255:
        assert isinstance(result, bytes)
        assert calls == ancestor + 2 * limit
    else:
        assert result == "default serializer exceeds recursion limit"
        assert calls == 255


@pytest.mark.parametrize("limit,siblings", [(255, 1), (256, 1), (255, 2)])
def test_default_container_counter_matches_orjson(limit, siblings, oracle):
    assert default_container_chain(jsonmodem, limit, siblings) == default_container_chain(
        oracle, limit, siblings
    )


@pytest.mark.parametrize("ancestor,limit", [(100, 155), (100, 156), (254, 1), (255, 1)])
def test_nonzero_default_counter_matches_orjson(ancestor, limit, oracle):
    assert default_container_chain(
        jsonmodem, limit, siblings=2, ancestor=ancestor
    ) == default_container_chain(oracle, limit, siblings=2, ancestor=ancestor)


@pytest.mark.parametrize("count", [2, 8, 16, 31, 64, 255])
def test_sorted_converted_key_duplicates_retain_input_order(count):
    pairs = [(key, index * 2 + variant) for index in range(count)
             for variant, key in enumerate((index, str(index)))]
    random.Random(1729).shuffle(pairs)
    value = dict(pairs)
    expected_pairs = sorted(((str(key), item) for key, item in pairs), key=lambda pair: pair[0])
    expected = "{" + ",".join(json.dumps(key) + ":" + str(item) for key, item in expected_pairs) + "}"
    option = jsonmodem.OPT_SORT_KEYS | jsonmodem.OPT_NON_STR_KEYS
    assert jsonmodem.dumps(value, option=option) == expected.encode()


@pytest.mark.parametrize("integer", [2**53, -(2**53), 2**64, -(2**63) - 1])
def test_dataclass_integer_options_do_not_change(integer):
    value = Record(integer, None)
    with pytest.raises(TypeError):
        jsonmodem.dumps(value, option=jsonmodem.OPT_STRICT_INTEGER)


@pytest.mark.parametrize("error_type", [ValueError, RuntimeError, KeyboardInterrupt])
def test_dataclass_default_preserves_exception_cause(error_type):
    error = error_type("default failed")

    def default(_):
        raise error

    with pytest.raises(TypeError) as raised:
        jsonmodem.dumps(Record(object(), None), default=default)
    assert raised.value.__cause__ is error


@pytest.mark.parametrize("default", [None, 1])
def test_dataclass_explicit_invalid_default_has_cause(default):
    value = Record(object(), None)
    with pytest.raises(TypeError) as raised:
        jsonmodem.dumps(value, default=default)
    assert isinstance(raised.value.__cause__, TypeError)
    with pytest.raises(TypeError) as absent:
        jsonmodem.dumps(value)
    assert absent.value.__cause__ is None


@pytest.mark.parametrize("name", ["Unknown", "\u03a9Value"])
@pytest.mark.parametrize("use_default", [False, True])
def test_unsupported_type_error_message_and_cause(name, use_default):
    value = type(name, (), {})()
    cause = ValueError("default failed")

    def default(_):
        raise cause

    kwargs = {"default": default} if use_default else {}
    with pytest.raises(TypeError) as raised:
        jsonmodem.dumps(value, **kwargs)
    assert str(raised.value) == "Type is not JSON serializable: " + name
    assert raised.value.__cause__ is (cause if use_default else None)


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux address-space accounting")
@pytest.mark.parametrize("headroom", [2, 16])
@pytest.mark.parametrize("use_default", [False, True])
def test_unsupported_type_error_allocation_failure_does_not_abort(headroom, use_default):
    code = f"headroom = {headroom!r}\nuse_default = {use_default!r}\n" + r'''
import gc
import os
import resource
import jsonmodem

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
name = "a" * 10000000
value = type(name, (), {})()
cause = ValueError("default failed")
calls = 0

def default(_):
    global calls
    calls += 1
    raise cause

kwargs = {"default": default} if use_default else {}
gc.collect()
original = resource.getrlimit(resource.RLIMIT_AS)
if not os.environ.get("JSONMODEM_MEMORY_RUNNER"):
    with open("/proc/self/statm") as statm:
        size = int(statm.read().split()[0]) * os.sysconf("SC_PAGE_SIZE")
    resource.setrlimit(resource.RLIMIT_AS, (size + headroom * 1024**2, original[1]))
try:
    jsonmodem.dumps(value, **kwargs)
except MemoryError:
    outcome = "MemoryError"
except TypeError as error:
    outcome = "TypeError"
    saved_error = error
else:
    raise AssertionError("unsupported value was serialized")
finally:
    resource.setrlimit(resource.RLIMIT_AS, original)
if outcome == "TypeError":
    assert str(saved_error) == "Type is not JSON serializable: " + name
    assert saved_error.__cause__ is (cause if use_default else None)
assert calls == int(use_default)
assert jsonmodem.dumps({"ok": True}) == b'{"ok":true}'
print(outcome)
'''
    result = run_python(code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() in ("MemoryError", "TypeError")


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux address-space accounting")
@pytest.mark.parametrize("kind", ["array", "dataclass", "sorted_dict"])
def test_snapshot_allocation_failure_does_not_abort(kind):
    code = f"kind = {kind!r}\n" + r'''
import dataclasses
import os
import resource
import jsonmodem

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
count = 128 if os.environ.get("JSONMODEM_MEMORY_RUNNER") else 500000
marker = object()
option = 0
if kind == "array":
    value = [marker] * count
elif kind == "dataclass":
    @dataclasses.dataclass
    class Record:
        value: object
    value = Record(marker)
    value.__dict__.update((f"k{i}", marker) for i in range(count))
else:
    class Mapping(dict):
        pass
    value = Mapping((f"k{i}", marker) for i in reversed(range(count)))
    option = jsonmodem.OPT_SORT_KEYS

original = resource.getrlimit(resource.RLIMIT_AS)
limited = False
if not os.environ.get("JSONMODEM_MEMORY_RUNNER"):
    with open("/proc/self/statm") as statm:
        size = int(statm.read().split()[0]) * os.sysconf("SC_PAGE_SIZE")
    resource.setrlimit(resource.RLIMIT_AS, (size + 256 * 1024, original[1]))
    limited = True

def restore():
    global limited
    if limited:
        resource.setrlimit(resource.RLIMIT_AS, original)
        limited = False

def default(_):
    # Restoring the limit before output isolates snapshot allocation failures.
    restore()
    return None

try:
    encoded = jsonmodem.dumps(value, default=default, option=option)
except MemoryError:
    outcome = "MemoryError"
else:
    assert encoded.count(b"null") == count + (kind == "dataclass")
    outcome = "success"
finally:
    restore()
print(outcome)
'''
    result = run_python(code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() in ("MemoryError", "success")


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux address-space accounting")
@pytest.mark.parametrize("headroom", [2, 4, 8, 16])
@pytest.mark.parametrize("kind", ["ascii", "escaped", "fragment"])
def test_callback_output_allocation_failure_does_not_abort(headroom, kind):
    code = f"headroom = {headroom!r}\nkind = {kind!r}\n" + r'''
import gc
import os
import resource
import jsonmodem

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
value = [object()] * 1000
if kind == "escaped":
    text = '"\\\n\x00' * 2500
    expected_size = 30003001
elif kind == "fragment":
    text = jsonmodem.Fragment(b'"' + b"a" * 10000 + b'"')
    expected_size = 10003001
else:
    text = "a" * 10000
    expected_size = 10003001
gc.collect()
original = resource.getrlimit(resource.RLIMIT_AS)
if not os.environ.get("JSONMODEM_MEMORY_RUNNER"):
    with open("/proc/self/statm") as statm:
        size = int(statm.read().split()[0]) * os.sysconf("SC_PAGE_SIZE")
    resource.setrlimit(resource.RLIMIT_AS, (size + headroom * 1024**2, original[1]))
try:
    encoded = jsonmodem.dumps(value, default=lambda _: text)
except MemoryError:
    outcome = "MemoryError"
else:
    assert len(encoded) == expected_size
    outcome = "success"
finally:
    resource.setrlimit(resource.RLIMIT_AS, original)
assert jsonmodem.dumps({"ok": True}) == b'{"ok":true}'
print(outcome)
'''
    result = run_python(code)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() in ("MemoryError", "success")
