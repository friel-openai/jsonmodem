"""Check decoded array boundaries, error cleanup, and allocation failures."""

import json
import os
import subprocess
import sys

import pytest

import jsonmodem


@pytest.mark.parametrize("length", [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65, 1000])
def test_array_storage_boundaries(length):
    values = [None, True, False, -123, 1.25, "text", {"k": 4}, [1, 2]]
    array = [values[index % len(values)] for index in range(length)]
    for document in (json.dumps(array), json.dumps({"data": array, "tail": [array]})):
        assert jsonmodem.loads(document) == json.loads(document)


@pytest.mark.parametrize("length", [7, 8, 9, 64, 1000])
def test_array_error_discards_partial_result(length):
    prefix = json.dumps([{"k": index} for index in range(length)]).encode()[:-1]
    for ending in (b",", b",]", b",null", b",{\"k\":", b",\"\\uD800\"]"):
        with pytest.raises(json.JSONDecodeError):
            jsonmodem.loads(prefix + ending)
    assert jsonmodem.loads(b"[1,2,3]") == [1, 2, 3]


@pytest.mark.skipif(
    sys.platform != "linux" or bool(os.environ.get("JSONMODEM_MEMORY_RUNNER")),
    reason="requires Linux address-space limits without ASan's shadow memory",
)
@pytest.mark.parametrize("headroom", [512 * 1024, 2 * 1024**2, 14 * 1024**2])
def test_array_allocation_failure_is_catchable(headroom):
    code = f'''
import gc, os, resource
import jsonmodem
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
count = 1000000
document = b"[" + b"null," * (count - 1) + b"null]"
assert jsonmodem.loads(b"[null]") == [None]
gc.collect()
with open("/proc/self/statm") as status:
    virtual_bytes = int(status.read().split()[0]) * os.sysconf("SC_PAGE_SIZE")
previous = resource.getrlimit(resource.RLIMIT_AS)
resource.setrlimit(resource.RLIMIT_AS, (virtual_bytes + {headroom}, previous[1]))
try:
    try:
        value = jsonmodem.loads(document)
        assert len(value) == count
        del value
    except MemoryError:
        pass
finally:
    resource.setrlimit(resource.RLIMIT_AS, previous)
assert jsonmodem.loads(b"[1,2,3]") == [1, 2, 3]
'''
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
