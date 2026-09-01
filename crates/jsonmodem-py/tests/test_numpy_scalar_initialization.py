"""Constructor callbacks must not become the defaults for scalar admission."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import jsonmodem
import pytest

pytest.importorskip("numpy")


@pytest.mark.parametrize("replacement", ["SCALAR_TYPES", "encode"])
@pytest.mark.parametrize("container", ["scalar", "list", "tuple"])
def test_constructor_helper_replacement_and_restoration(replacement, container):
    code = r'''
import hashlib
import json
import os
from pathlib import Path
import sys

import jsonmodem
import numpy as np
from jsonmodem import _jsonmodem as native

if os.environ.get("JSONMODEM_MEMORY_RUNNER"):
    import ctypes
    assert getattr(ctypes.CDLL(None), "__asan_init")
assert "jsonmodem._numpy" not in sys.modules

replacement = sys.argv[1]
container = sys.argv[2]
constructor = native._NumericScalarTypes
initial = {}
calls = []
value = np.int64(7)
count = 1 if container == "scalar" else 65
payload = value if container == "scalar" else [value] * count
if container == "tuple":
    payload = tuple(payload)

def expected(token):
    if container == "scalar":
        return token
    return b"[" + b",".join([token] * count) + b"]"

def encode(item, option, default_provided, depth):
    assert item is value
    calls.append("encode")
    return b"123"

def default(item):
    assert item is value
    calls.append("default")
    return 123

def initialize(numpy, scalar_types):
    table = constructor(numpy, scalar_types)
    module = sys.modules["jsonmodem._numpy"]
    initial["SCALAR_TYPES"] = scalar_types
    initial["encode"] = module.encode
    setattr(module, replacement, () if replacement == "SCALAR_TYPES" else encode)
    return table

native._NumericScalarTypes = initialize
try:
    from jsonmodem import _compat, _numpy
finally:
    native._NumericScalarTypes = constructor

try:
    first = jsonmodem.dumps(payload, option=16, default=default)
    first_calls = list(calls)
finally:
    setattr(_numpy, replacement, initial[replacement])
calls.clear()
restored = jsonmodem.dumps(payload, option=16, default=default)
helpers = _compat._ENCODER_HELPERS[13]
identity = {
    "case": replacement,
    "container": container,
    "pid": os.getpid(),
    "python": str(Path(sys.executable).resolve()),
    "package": str(Path(jsonmodem.__file__).resolve()),
    "native": str(Path(native.__file__).resolve()),
    "native_sha256": hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
    "helper": str(Path(_numpy.__file__).resolve()),
    "helper_sha256": hashlib.sha256(Path(_numpy.__file__).read_bytes()).hexdigest(),
    "first": first.decode("ascii"),
    "first_calls": first_calls,
    "restored": restored.decode("ascii"),
    "restored_calls": calls,
    "initial_scalar_types_retained": helpers[7] is initial["SCALAR_TYPES"],
    "initial_encode_retained": helpers[4] is initial["encode"],
}
print(json.dumps(identity), flush=True)
assert first == expected(b"123"), identity
assert first_calls == ["default" if replacement == "SCALAR_TYPES" else "encode"] * count, identity
assert restored == expected(b"7") and not calls, identity
assert identity["initial_scalar_types_retained"], identity
assert identity["initial_encode_retained"], identity
'''
    runner = os.environ.get("JSONMODEM_MEMORY_RUNNER")
    command = [runner] if runner else []
    process = subprocess.run(
        [*command, sys.executable, "-B", "-c", code, replacement, container],
        capture_output=True, text=True, timeout=30,
    )
    print(process.stdout, end="")
    assert process.returncode == 0, process.stdout + process.stderr
    identity = json.loads(process.stdout)
    assert identity["python"] == str(Path(sys.executable).resolve())
    assert identity["package"] == str(Path(jsonmodem.__file__).resolve())
    assert identity["native"] == str(Path(jsonmodem._native.__file__).resolve())
    assert identity["native_sha256"] == hashlib.sha256(
        Path(jsonmodem._native.__file__).read_bytes()
    ).hexdigest()
    helper = Path(jsonmodem.__file__).resolve().with_name("_numpy.py")
    assert identity["helper"] == str(helper)
    assert identity["helper_sha256"] == hashlib.sha256(helper.read_bytes()).hexdigest()
