"""C-contiguous memoryviews are copied before complete-document decoding."""

import array
import ctypes
import gc
import json
import mmap

import pytest
import jsonmodem

try:
    import orjson
except ImportError:
    orjson = None

MODULES = (jsonmodem,) if orjson is None else (jsonmodem, orjson)


def assert_loads(view, expected):
    for module in MODULES:
        assert module.loads(view) == expected


@pytest.mark.parametrize("data", [b"[1]", b'{"text":"hello"}', b'"\xc3\xa9"'])
def test_array_memoryview(data):
    backing = array.array("B", data)
    for view in (memoryview(backing), memoryview(backing).toreadonly()):
        assert_loads(view, json.loads(data))


def test_native_memoryview_without_python_owner():
    data = b'{"number":9007199254740993}'
    backing = ctypes.create_string_buffer(data)
    make_view = ctypes.pythonapi.PyMemoryView_FromMemory
    make_view.argtypes = (ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_int)
    make_view.restype = ctypes.py_object
    # Keep backing alive: a raw native view does not retain the allocation.
    view = make_view(ctypes.addressof(backing), len(data), 0x100)
    assert view.obj is None
    assert_loads(view, {"number": 9007199254740993})
    assert backing.value == data


def test_mapped_memoryview():
    with mmap.mmap(-1, 4096) as backing:
        backing[:7] = b"[1,2,3]"
        with memoryview(backing)[:7] as view:
            assert_loads(view, [1, 2, 3])


def test_multidimensional_memoryview():
    backing = array.array("B", b"[1,2,3] ")
    view = memoryview(backing).cast("B", shape=(2, 4))
    assert_loads(view, [1, 2, 3])


def test_typed_memoryview_uses_raw_bytes():
    backing = array.array("B", b"[1] ")
    view = memoryview(backing).cast("I")
    assert_loads(view, [1])


def test_ctypes_memoryview():
    backing = (ctypes.c_char * 3)(*b"[1]")
    view = memoryview(backing)
    assert_loads(view, [1])


def test_zero_dimensional_memoryview():
    view = memoryview(b"1").cast("B", shape=())
    assert_loads(view, 1)


@pytest.mark.parametrize("format", ["B", "b", "c"])
def test_contiguous_slice_excludes_other_bytes(format):
    backing = array.array("B", b"invalid[1]invalid")
    view = memoryview(backing).cast(format)[7:10]
    assert_loads(view, [1])


def test_one_element_reversed_view_is_contiguous():
    view = memoryview(array.array("B", b"1"))[::-1]
    assert view.c_contiguous
    assert_loads(view, 1)


def test_fortran_only_memoryview_is_rejected():
    np = pytest.importorskip("numpy")
    view = memoryview(np.array([[91, 49], [93, 32]], dtype=np.uint8, order="F"))
    assert view.f_contiguous and not view.c_contiguous
    for module in MODULES:
        with pytest.raises(module.JSONDecodeError):
            module.loads(view)


@pytest.mark.parametrize("readonly", [False, True])
@pytest.mark.parametrize("external", [False, True])
def test_gc_can_release_and_clear_original_buffer(readonly, external):
    data = b"[" + b",".join([b"{}"] * 2000) + b"]"
    backing = array.array("B", data) if external else bytearray(data)
    view = memoryview(backing)
    if readonly:
        view = view.toreadonly()
    released = False

    def release_input(phase, info):
        nonlocal released
        if phase == "start" and not released:
            released = True
            view.release()
            del backing[:]

    gc.collect()
    thresholds = gc.get_threshold()
    gc.callbacks.append(release_input)
    try:
        gc.set_threshold(10, 100000, 100000)
        result = jsonmodem.loads(view)
    finally:
        gc.callbacks.remove(release_input)
        gc.set_threshold(*thresholds)
    assert result == [{}] * 2000
    assert released and not backing


def test_released_contiguous_memoryview():
    view = memoryview(b"[1]")
    view.release()
    # The reference may read stale metadata after release. Do not reproduce it.
    with pytest.raises(jsonmodem.JSONDecodeError):
        jsonmodem.loads(view)


@pytest.mark.parametrize("released", [False, True])
def test_unreadable_memoryview_raises_decode_error(released):
    backing = array.array("B", b"[ 1 ] ")
    view = memoryview(backing)[::2]
    if released:
        view.release()
    for module in MODULES:
        with pytest.raises(module.JSONDecodeError):
            module.loads(view)


@pytest.mark.parametrize("data", [b"", b"[1,]", b'"\xff"', b"1e400"])
def test_invalid_json_in_external_memoryview(data):
    view = memoryview(array.array("B", data))
    for module in MODULES:
        with pytest.raises(module.JSONDecodeError):
            module.loads(view)
