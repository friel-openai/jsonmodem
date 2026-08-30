"""Profile complete-document calls separately from uninstrumented benchmarks."""

import argparse
import array
import cProfile
import dataclasses
import gc
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import orjson

# Python's safe-path mode omits the script directory from module lookup.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from allocation_stats import summarize_allocations

spec = importlib.util.spec_from_file_location(
    "bench_orjson_compat", Path(__file__).with_name("bench_orjson_compat.py")
)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
PAYLOADS = benchmark.PAYLOADS


@dataclasses.dataclass
class Record:
    """Synthetic dataclass payload shared by both serializers."""

    id: int
    name: str


WORKLOADS = (
    "loads_medium", "loads_integers", "loads_floats", "loads_strings", "loads_escaped",
    "loads_small_view", "loads_escaped_first", "loads_bmp", "loads_unicode_escapes",
    "loads_invalid_utf8", "dumps_medium", "dumps_integers",
    "dumps_escaped", "dumps_long_string", "sorted_medium", "dataclasses_1000",
    "numpy_float32", "late_default",
)


def workload(module, name):
    if name == "loads_bmp":
        return module.loads, orjson.dumps("\u2603" * 43690), {}
    if name == "loads_unicode_escapes":
        return module.loads, json.dumps(["\u2603\U0001f600"] * 1000).encode(), {}
    if name == "loads_invalid_utf8":
        valid_bytes = 8 * 1024 * 1024 - 3
        value = (b'"' + b"\xe2\x98\x83" * (valid_bytes // 3)
                 + b"x" * (valid_bytes % 3) + b'\xff"')

        def reject(document):
            try:
                module.loads(document)
            except module.JSONDecodeError as error:
                assert error.doc == "" and error.pos == 0
            else:
                raise AssertionError("invalid UTF-8 was accepted")

        return reject, value, {}
    if name == "loads_escaped_first":
        value = ["x" * (1 << 20) + "\n", *range(250000)]
        return module.loads, orjson.dumps(value), {}
    if name.startswith("loads_") and name != "loads_small_view":
        return module.loads, orjson.dumps(PAYLOADS[name.removeprefix("loads_")]), {}
    if name == "loads_small_view":
        value = memoryview(array.array("B", orjson.dumps(PAYLOADS["small"])))
        return module.loads, value, {}
    if name.startswith("dumps_"):
        return module.dumps, PAYLOADS[name.removeprefix("dumps_")], {}
    if name == "sorted_medium":
        value = [{"id": i, "score": i / 7, "name": f"item-{i}"} for i in range(1000)]
        return module.dumps, value, {"option": module.OPT_SORT_KEYS}
    if name == "dataclasses_1000":
        return module.dumps, [Record(i, f"item-{i}") for i in range(1000)], {}
    if name == "numpy_float32":
        import numpy as np

        value = np.arange(100000, dtype=np.float32).reshape(25000, 4)
        return module.dumps, value, {"option": module.OPT_SERIALIZE_NUMPY}
    return module.dumps, ["x" * 4096] * 5000 + [object()], {"default": lambda _: None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=("jsonmodem", "orjson"), required=True)
    parser.add_argument("--workload", choices=WORKLOADS, required=True)
    parser.add_argument("--mode", choices=("loop", "cprofile", "memray"), required=True)
    parser.add_argument("--output", help="Required for cprofile and memray")
    parser.add_argument("--calls", type=int, default=1000)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--text-input", action="store_true",
                        help="Use warmed Python str input for a byte-based loads workload")
    args = parser.parse_args()
    if args.calls < 1 or args.seconds <= 0:
        parser.error("calls and seconds must be positive")
    if args.mode != "loop" and not args.output:
        parser.error("--output is required for a saved profile")
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    module = importlib.import_module(args.module)
    function, value, kwargs = workload(module, args.workload)
    reference, reference_value, reference_kwargs = workload(orjson, args.workload)
    if args.text_input:
        if args.workload == "loads_invalid_utf8":
            parser.error("malformed UTF-8 has no str representation")
        if not args.workload.startswith("loads_") or not isinstance(value, bytes):
            parser.error("--text-input requires a byte-based loads workload")
        value = value.decode("utf-8")
        reference_value = reference_value.decode("utf-8")
    assert function(value, **kwargs) == reference(reference_value, **reference_kwargs)
    for _ in range(10):
        function(value, **kwargs)
    gc.collect()

    def run():
        for _ in range(args.calls):
            function(value, **kwargs)

    enabled = gc.isenabled()
    gc.disable()
    try:
        if args.mode == "loop":
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                run()
        elif args.mode == "cprofile":
            profiler = cProfile.Profile()
            profiler.runcall(run)
            profiler.dump_stats(args.output)
        else:
            import memray

            with memray.Tracker(args.output, native_traces=True, trace_python_allocators=True):
                run()
            summary = summarize_allocations(args.output)
            result = {"module": args.module, "version": module.__version__,
                      "module_file": module.__file__, "gc_disabled": True,
                      "workload": args.workload, "input_type": type(value).__name__,
                      "calls": args.calls,
                      "allocation_events": summary["allocation_requests"],
                      "allocated_bytes": summary["total_allocated_bytes"],
                      "peak_live_bytes": summary["peak_live_bytes"]}
            Path(args.output + ".json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result))
    finally:
        if enabled:
            gc.enable()


if __name__ == "__main__":
    main()
