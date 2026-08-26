"""Measure complete-call allocation events and peak live bytes with Memray."""

import argparse
import dataclasses
import gc
import importlib
import json
import os
import platform
from pathlib import Path

import memray
import numpy
import orjson


@dataclasses.dataclass
class Record:
    id: int
    name: str


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", default="jsonmodem", choices=["jsonmodem", "orjson"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--calls", type=int, default=100)
    parser.add_argument("--workload", help="Profile only the named workload")
    args = parser.parse_args()
    module = importlib.import_module(args.module)
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    medium = [{"id": i, "score": i / 7, "name": f"item-{i}"} for i in range(1000)]
    small = {"id": 42, "ok": True, "name": "jsonmodem", "tags": ["a", "b", "c"]}
    fragment = module.Fragment(b'{"x":[1,2,3]}')
    cases = [
        ("loads_medium", module.loads, orjson.dumps(medium), {}),
        ("dumps_small", module.dumps, small, {}),
        ("dumps_medium", module.dumps, medium, {}),
        ("long_string", module.dumps, "abcdefghijklmnopqrstuvxyz0123456789" * 4096, {}),
        ("sorted_medium", module.dumps, medium, {"option": module.OPT_SORT_KEYS}),
        ("fragments_1000", module.dumps, [fragment] * 1000, {}),
        ("dataclasses_1000", module.dumps, [Record(i, f"item-{i}") for i in range(1000)], {}),
        ("numpy_float32", module.dumps, numpy.arange(100000, dtype=numpy.float32).reshape(25000, 4), {"option": module.OPT_SERIALIZE_NUMPY}),
        ("late_default", module.dumps, ["x" * 4096] * 5000 + [object()], {"default": lambda _: None}),
    ]
    if args.workload:
        cases = [case for case in cases if case[0] == args.workload]
        if not cases:
            parser.error("unknown workload")
    result = {"python": platform.python_version(), "module": args.module,
              "version": module.__version__, "memray": memray.__version__,
              "numpy": numpy.__version__, "calls": args.calls, "cases": []}
    for name, function, value, kwargs in cases:
        for _ in range(10):
            function(value, **kwargs)
        gc.collect()
        profile = str(Path(args.output).with_suffix(f".{name}.bin"))
        with memray.Tracker(profile, trace_python_allocators=True):
            for _ in range(args.calls):
                function(value, **kwargs)
        reader = memray.FileReader(profile)
        events = allocated = 0
        for record in reader.get_allocation_records():
            if record.size > 0:
                events += record.n_allocations
                allocated += record.size
        peak = sum(record.size for record in reader.get_high_watermark_allocation_records())
        measurement = {"name": name, "allocation_events": events,
                       "allocated_bytes": allocated, "peak_live_bytes": peak}
        result["cases"].append(measurement)
        print(json.dumps(measurement), flush=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
