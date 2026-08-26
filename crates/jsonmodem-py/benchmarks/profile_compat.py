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
import time

import orjson

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
    "loads_medium", "loads_integers", "loads_floats", "loads_small_view", "dumps_medium", "dumps_integers",
    "dumps_escaped", "dumps_long_string", "sorted_medium", "dataclasses_1000",
    "numpy_float32", "late_default",
)


def workload(module, name):
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
    assert function(value, **kwargs) == reference(reference_value, **reference_kwargs)
    for _ in range(10):
        function(value, **kwargs)
    gc.collect()

    def run():
        for _ in range(args.calls):
            function(value, **kwargs)

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
        reader = memray.FileReader(args.output)
        events = allocated = 0
        for record in reader.get_allocation_records():
            if record.size > 0:
                events += record.n_allocations
                allocated += record.size
        peak = sum(record.size for record in reader.get_high_watermark_allocation_records())
        result = {"module": args.module, "version": module.__version__,
                  "workload": args.workload, "calls": args.calls,
                  "allocation_events": events, "allocated_bytes": allocated,
                  "peak_live_bytes": peak}
        Path(args.output + ".json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
