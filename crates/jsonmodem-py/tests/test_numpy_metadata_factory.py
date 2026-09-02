"""Scalar metadata does not depend on replaceable NumPy factory functions."""

from pathlib import Path
import os
import subprocess
import sys

import jsonmodem
import pytest

np = pytest.importorskip("numpy")


@pytest.mark.parametrize("name", ("int64", "float32"))
@pytest.mark.parametrize("behavior", ("raises", "lies"))
def test_replaced_dtype_factory_before_first_numpy_encode(name, behavior):
    code = """
from pathlib import Path
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])
import jsonmodem
import numpy as np

assert Path(jsonmodem._native.__file__).resolve() == Path(sys.argv[2]).resolve()
if os.environ.get('JSONMODEM_MEMORY_RUNNER'):
    import ctypes
    assert getattr(ctypes.CDLL(None), '__asan_init')
assert 'jsonmodem._numpy' not in sys.modules
value = getattr(np, sys.argv[3])(7)
expected = b'7' if sys.argv[3] == 'int64' else b'7.0'

def replacement(scalar_type):
    if sys.argv[4] == 'raises':
        raise AssertionError('dtype factory called')
    return SimpleNamespace(type=scalar_type, isnative=True, kind='f', itemsize=8)

np.dtype = replacement
assert jsonmodem.dumps(value, option=jsonmodem.OPT_SERIALIZE_NUMPY) == expected
"""
    runner = os.environ.get("JSONMODEM_MEMORY_RUNNER")
    command = [runner] if runner else []
    result = subprocess.run(
        [*command, sys.executable, "-B", "-W", "error", "-c", code,
         str(Path(jsonmodem.__file__).resolve().parent.parent),
         jsonmodem._native.__file__, name, behavior],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_metadata_discovery_skips_abstract_and_datetime_types(monkeypatch):
    from jsonmodem import _numpy

    def unavailable(*args, **kwargs):
        raise AssertionError("dtype factory called")

    monkeypatch.setattr(np, "dtype", unavailable)
    numeric = (np.bool_, np.int64, np.longlong, np.ulonglong, np.float64)
    monkeypatch.setattr(_numpy, "SCALAR_TYPES", numeric + (
        np.datetime64, np.timedelta64, np.generic, np.integer, int,
    ))
    metadata = _numpy._numeric_scalar_metadata()
    eligible = sys.implementation.name == "cpython" and bool(np.int64.__flags__ & (1 << 8))
    expected = {scalar_type: (scalar_type(0).dtype.kind, scalar_type(0).dtype.itemsize)
                for scalar_type in numeric} if eligible else {}
    assert metadata == expected
