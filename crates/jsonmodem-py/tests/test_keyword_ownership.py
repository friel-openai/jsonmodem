"""Keep constructor arguments alive when valid C API calls share a kwargs dict."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

import jsonmodem


_CHILD = r'''
import codecs
import ctypes
import gc
from pathlib import Path
import sys
import threading
import weakref

case, package, native = sys.argv[1:]
sys.path.insert(0, package)
import jsonmodem
assert Path(jsonmodem._native.__file__).resolve() == Path(native).resolve()
call = ctypes.pythonapi.PyObject_Call
call.argtypes = [ctypes.py_object, ctypes.py_object, ctypes.py_object]
call.restype = ctypes.py_object

class Victim(dict):
    pass

class Abort(Exception):
    pass

victim = Victim()
reference = weakref.ref(victim)
observations = []
entered = threading.Event()
changed = threading.Event()

class bool_:
    __module__ = "numpy"

    def __bool__(self):
        if case == "thread":
            entered.set()
            assert changed.wait(10)
        else:
            shared.clear()
        observations.append(reference() is not None)
        # Abort before any later argument could be read from a broken binding.
        raise Abort()

trigger = bool_()
key = chr(0xD800)
if case == "codec":
    shared = {"options": victim, key: None}
    constructor = jsonmodem.JsonModem
    expected = TypeError
else:
    shared = {"allow_unicode_whitespace": trigger, "decode_mode": victim}
    constructor = jsonmodem.ParserOptions
    expected = Abort
del victim

def strict(error):
    assert error.object is key
    shared.clear()
    observations.append(reference() is not None)
    raise Abort()

def mutate():
    if entered.wait(10):
        shared.clear()
        changed.set()

thread = threading.Thread(target=mutate) if case == "thread" else None
original = codecs.lookup_error("strict")
try:
    if case == "codec":
        codecs.register_error("strict", strict)
    if thread is not None:
        thread.start()
    try:
        call(constructor, (), shared)
    except expected:
        pass
    else:
        raise AssertionError("conversion did not abort")
finally:
    codecs.register_error("strict", original)
    if thread is not None:
        thread.join(12)
        assert not thread.is_alive() and changed.is_set()
gc.collect()
assert observations and all(observations), observations
assert reference() is None, "argument snapshot leaked its owner"
assert jsonmodem.dumps({"after": 1}) == b'{"after":1}'
print("keyword owners survived reentry and were released")
'''


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython shared-kwargs C API")
@pytest.mark.parametrize("case", ["codec", "argument", "thread"])
def test_shared_keyword_values_survive_reentry(case):
    package = Path(jsonmodem.__file__).resolve().parent.parent
    native = Path(jsonmodem._native.__file__).resolve()
    runner = os.environ.get("JSONMODEM_MEMORY_RUNNER")
    command = [runner] if runner else []
    result = subprocess.run(
        [*command, sys.executable, "-B", "-c", _CHILD, case, str(package), str(native)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "keyword owners survived reentry and were released"
