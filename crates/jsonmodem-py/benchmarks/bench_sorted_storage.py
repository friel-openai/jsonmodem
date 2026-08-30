"""Compare sorted dictionary output and its temporary allocation requirements."""

import argparse
import gc
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import sys

# Python's safe-path mode omits the script directory from module lookup.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from allocation_stats import summarize_allocations

spec = importlib.util.spec_from_file_location(
    "bench_output_buffers", Path(__file__).with_name("bench_output_buffers.py")
)
output_benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(output_benchmark)


def cases():
    result = {}
    for count, batch in ((0, 1000), (1, 1000), (4, 1000), (8, 1000),
                         (16, 1000), (64, 100), (65, 100), (1000, 10)):
        keys = [f"key-{i:04d}" for i in range(count)]
        random.Random(1729).shuffle(keys)
        result[f"keys_{count}"] = [
            dict(zip(keys, range(i, i + count))) for i in range(batch)
        ]
    small = result["keys_4"]
    result["nested"] = [{"nested": item, "value": i} for i, item in enumerate(small)]
    large = {f"key-{i:05d}": i for i in reversed(range(10000))}
    result["large_first"] = [large, *small]
    result["large_last"] = [*small, large]
    preload = {f"{i:02x}": 0 for i in range(64)}
    chain = 0
    for _ in range(128):
        chain = {"a": preload, "b": chain}
    result["nested_preload"] = chain
    return result


def worker(args):
    package = Path(args.package).resolve()
    sys.path.insert(0, str(package))
    import jsonmodem
    import orjson

    assert Path(jsonmodem.__file__).resolve().is_relative_to(package)
    assert Path(jsonmodem._native.__file__).resolve().is_relative_to(package)
    workloads = cases()
    if args.cases:
        unknown = set(args.cases) - workloads.keys()
        if unknown:
            raise ValueError(f"unknown cases: {sorted(unknown)}")
        workloads = {name: value for name, value in workloads.items() if name in args.cases}
    result = {"package": jsonmodem.__file__, "extension": jsonmodem._native.__file__,
              "python": platform.python_version(), "orjson": orjson.__version__,
              "cases": {}}
    if args.mode == "timing":
        spec = importlib.util.spec_from_file_location(
            "bench_orjson_compat", Path(__file__).with_name("bench_orjson_compat.py")
        )
        benchmark = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(benchmark)

        for name, value in workloads.items():
            ours = lambda obj: jsonmodem.dumps(obj, option=jsonmodem.OPT_SORT_KEYS)
            theirs = lambda obj: orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
            assert ours(value) == theirs(value), name
            result["cases"][name] = benchmark.measure(ours, theirs, value, 3, args.seconds)
        return result

    import memray

    module = jsonmodem if args.library == "jsonmodem" else orjson
    result.update(library=args.library, library_version=module.__version__,
                  memray=memray.__version__, calls=args.calls, gc_disabled=True)
    for name, value in workloads.items():
        kwargs = {"option": module.OPT_SORT_KEYS}
        assert module.dumps(value, **kwargs) == orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
        for _ in range(10):
            module.dumps(value, **kwargs)
        gc.collect()
        enabled = gc.isenabled()
        gc.disable()
        profile = str(Path(args.output).with_suffix(f".{name}.memray"))
        try:
            with memray.Tracker(profile, native_traces=True, trace_python_allocators=True):
                for _ in range(args.calls):
                    module.dumps(value, **kwargs)
        finally:
            if enabled:
                gc.enable()
        summary = summarize_allocations(profile)
        result["cases"][name] = {"allocation_events": summary["allocation_requests"],
                                 "allocated_bytes": summary["total_allocated_bytes"],
                                 "peak_live_bytes": summary["peak_live_bytes"]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-package")
    parser.add_argument("--candidate-package")
    parser.add_argument("--package", help=argparse.SUPPRESS)
    parser.add_argument("--output")
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument("--seconds", type=float, default=0.03)
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--mode", choices=("timing", "memray"), default="timing")
    parser.add_argument("--library", choices=("jsonmodem", "orjson"), default="jsonmodem")
    parser.add_argument("--calls", type=int, default=30)
    args = parser.parse_args()
    if args.pairs < 1 or args.seconds <= 0 or args.calls < 1:
        parser.error("pairs, seconds and calls must be positive")
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    if args.mode == "memray" and (not args.package or not args.output):
        parser.error("memray requires package and output")
    if args.package:
        result = worker(args)
        if args.mode == "memray":
            Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    else:
        if not args.baseline_package or not args.candidate_package or not args.output:
            parser.error("baseline-package, candidate-package and output are required")
        Path(args.output).write_text(json.dumps(output_benchmark.compare(args, __file__), indent=2) + "\n")


if __name__ == "__main__":
    main()
