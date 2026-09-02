"""GC callbacks must not observe partially initialized path tuples."""

import os
import platform
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.skipif(platform.python_implementation() != "CPython", reason="CPython C API")
@pytest.mark.parametrize("operation", ["as_tuple", "slice", "byte_views"])
def test_path_tuples_are_complete_during_gc(operation):
    code = textwrap.dedent(
        """
        import ctypes
        import gc
        import jsonmodem
        import sys

        if sys.platform != "win32":
            import resource
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        get_item = ctypes.pythonapi.PyTuple_GetItem
        get_item.argtypes = [ctypes.py_object, ctypes.c_ssize_t]
        get_item.restype = ctypes.c_void_p
        operation = sys.argv[1]
        depth = 37
        source = b"[" * depth + b"0" + b"]" * depth
        gc.disable()
        parser = jsonmodem.JsonModem()
        events = list(parser.feed(source)) + list(parser.finish())
        path = next(path for kind, path, value in events if kind == "number")
        assert len(path) == depth
        observed = []
        scans = 0

        def inspect(phase, info):
            global scans
            if phase != "start" or observed:
                return
            scans += 1
            for obj in gc.get_objects():
                if type(obj) is tuple and len(obj) == depth:
                    for index in range(depth):
                        # Do not index or retain a tuple containing NULL slots.
                        # The public getter returns its pointer without dereferencing it.
                        if get_item(obj, index) is None:
                            observed.append(index)
                            return

        for threshold in (1, 2, 5, 17):
            gc.collect()
            gc.set_threshold(threshold, 100000, 100000)
            parser = jsonmodem.JsonModem(byte_views=True)
            gc.callbacks.append(inspect)
            gc.enable()
            try:
                if operation == "as_tuple":
                    result = path.as_tuple()
                elif operation == "slice":
                    result = path[:]
                else:
                    result = list(parser.feed(source))
                gc.collect()
            finally:
                gc.disable()
                gc.callbacks.remove(inspect)
            assert not observed, (operation, threshold, observed)
        assert scans > 0
        """
    )
    runner = os.environ.get("JSONMODEM_MEMORY_RUNNER")
    command = [runner] if runner else []
    result = subprocess.run(
        [*command, sys.executable, "-c", code, operation],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("step", [sys.maxsize, -sys.maxsize, -(sys.maxsize + 1)])
def test_path_slice_with_large_step(step):
    import jsonmodem

    parser = jsonmodem.JsonModem()
    path = next(path for kind, path, value in parser.feed(b"[[0]]") if kind == "number")
    assert path[::step] == path.as_tuple()[::step]
