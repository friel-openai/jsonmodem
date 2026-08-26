"""Compare complete-document numeric conversion, separately from streaming."""

import argparse
import gc
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import struct
import subprocess
import sys
import time


def workloads(orjson):
    rng = random.Random(4813)
    values = {
        "small": {"id": 42, "active": True, "name": "record"},
        "medium": [{"id": i, "score": i / 7, "name": f"item-{i}"} for i in range(1000)],
        "integers": list(range(-5000, 5000)),
        "random_small": [rng.randrange(-10000, 10000) for _ in range(10000)],
        "wide_signed": [rng.randrange(-(2**63), 2**63) for _ in range(10000)],
        "wide_unsigned": [rng.randrange(2**63, 2**64) for _ in range(10000)],
        "mixed_integers": [rng.randrange(-(2**63), 2**64) for _ in range(10000)],
        "tiny_integers": [0, -1, 10, -100, 999],
        "scalar_integer": 123456789,
        "floats": [i / 7 for i in range(10000)],
    }
    floats = [struct.unpack("<d", rng.getrandbits(64).to_bytes(8, "little"))[0] for _ in range(10000)]
    values["float_bits"] = [value for value in floats if math.isfinite(value)]
    documents = {name: orjson.dumps(value) for name, value in values.items()}
    documents["overflow_integers"] = (
        "[" + ",".join(str(rng.randrange(-(2**200), 2**200)) for _ in range(10000)) + "]"
    ).encode()
    documents["long_fractions"] = (
        b"[" + b",".join([b"1.23456789012345678901234567890123456789", b"-0.0000000000000000000000000000000000000123456789"] * 5000) + b"]"
    )
    documents["zero_forms"] = b"[0,-0,0.0,-0.0,0e0,-0e0,0.0e-999,-0.0e-999]"
    return values, documents


def prepare(args):
    package = Path(args.package).resolve()
    sys.path.insert(0, str(package))
    import jsonmodem
    import orjson

    assert Path(jsonmodem.__file__).resolve().is_relative_to(package)
    assert Path(jsonmodem._native.__file__).resolve().is_relative_to(package)
    spec = importlib.util.spec_from_file_location(
        "bench_orjson_compat", Path(__file__).with_name("bench_orjson_compat.py")
    )
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    values, documents = workloads(orjson)
    unknown = set(args.cases or ()) - (values.keys() | documents.keys())
    if unknown:
        raise ValueError(f"unknown cases: {sorted(unknown)}")
    cases = {}
    for operation in args.operations:
        inputs = documents if operation == "loads" else values
        for name, value in inputs.items():
            if args.cases and name not in args.cases:
                continue
            ours = getattr(jsonmodem, operation)
            reference = getattr(orjson, operation)
            actual, expected = ours(value), reference(value)
            if operation == "loads":
                assert orjson.dumps(actual) == orjson.dumps(expected), (operation, name)
            else:
                assert actual == expected, (operation, name)
            cases[f"{operation}_{name}"] = (ours, reference, value)
    return jsonmodem, orjson, benchmark, cases


def worker(args):
    module, orjson, benchmark, cases = prepare(args)
    return {
        "package": module.__file__, "extension": module._native.__file__,
        "python": platform.python_version(), "orjson": orjson.__version__,
        "hash_seed": os.environ.get("PYTHONHASHSEED"),
        "cases": {name: benchmark.measure(ours, reference, value, 3, args.seconds)
                  for name, (ours, reference, value) in cases.items()},
    }


def profile(args):
    module, orjson, _, cases = prepare(args)
    if len(cases) != 1:
        raise ValueError("select one operation and one case for profiling")
    name, (ours, reference, value) = next(iter(cases.items()))
    function = ours if args.module == "jsonmodem" else reference
    for _ in range(10):
        function(value)
    gc.collect()

    def run():
        for _ in range(args.calls):
            function(value)

    gc_enabled = gc.isenabled()
    gc.disable()
    try:
        if args.profile == "loop":
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                run()
            return
        import memray

        with memray.Tracker(args.output, native_traces=True, trace_python_allocators=True):
            run()
    finally:
        if gc_enabled:
            gc.enable()
    reader = memray.FileReader(args.output)
    events = allocated = 0
    for record in reader.get_allocation_records():
        if record.size > 0:
            events += record.n_allocations
            allocated += record.size
    result = {
        "package": module.__file__ if args.module == "jsonmodem" else orjson.__file__,
        "jsonmodem_package": module.__file__, "module": args.module, "case": name,
        "python": platform.python_version(), "orjson": orjson.__version__, "calls": args.calls,
        "hash_seed": os.environ.get("PYTHONHASHSEED"),
        "gc_disabled": True,
        "allocation_events": events, "allocated_bytes": allocated,
        "peak_live_bytes": sum(record.size for record in reader.get_high_watermark_allocation_records()),
    }
    Path(args.output + ".json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


def compare(args):
    packages = {"baseline": args.baseline_package, "candidate": args.candidate_package}
    runs = {name: [] for name in packages}
    seeds = [(args.hash_seed + pair) % (2**32) for pair in range(args.pairs)]
    for pair in range(args.pairs):
        environment = {**os.environ, "PYTHONHASHSEED": str(seeds[pair])}
        order = list(packages) if pair % 2 == 0 else list(reversed(packages))
        for name in order:
            command = [sys.executable, __file__, "--package", packages[name],
                       "--seconds", str(args.seconds), "--operations", *args.operations]
            if args.cases:
                command.extend(["--cases", *args.cases])
            runs[name].append(json.loads(subprocess.check_output(command, text=True, env=environment)))
        print(f"Completed comparison {pair + 1} of {args.pairs}", flush=True)
    summary = {}
    for name in runs["baseline"][0]["cases"]:
        samples = {package: [run["cases"][name] for run in records] for package, records in runs.items()}
        paired = [new["jsonmodem_ns"] / old["jsonmodem_ns"]
                  for old, new in zip(samples["baseline"], samples["candidate"])]
        summary[name] = {
            "candidate_over_baseline": statistics.median(paired),
            "ratio_range": [min(paired), max(paired)], "paired_ratios": paired,
            "ns": {package: statistics.median(row["jsonmodem_ns"] for row in rows)
                   for package, rows in samples.items()},
            "orjson_ns": {package: statistics.median(row["orjson_ns"] for row in rows)
                          for package, rows in samples.items()},
            "over_orjson": {package: statistics.median(row["ratio"] for row in rows)
                            for package, rows in samples.items()},
        }
        print(f"{name}: candidate / baseline = {statistics.median(paired):.3f}", flush=True)
    return {"cpu": min(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "pairs": args.pairs, "seconds": args.seconds, "hash_seeds": seeds,
            "summary": summary, "runs": runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-package")
    parser.add_argument("--candidate-package")
    parser.add_argument("--package", help=argparse.SUPPRESS)
    parser.add_argument("--output")
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument("--hash-seed", type=int, default=1729,
                        help="First paired PYTHONHASHSEED; incremented for each comparison")
    parser.add_argument("--seconds", type=float, default=0.03)
    parser.add_argument("--operations", nargs="+", choices=("loads", "dumps"), default=["loads", "dumps"])
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--profile", choices=("loop", "memray"))
    parser.add_argument("--module", choices=("jsonmodem", "orjson"), default="jsonmodem")
    parser.add_argument("--calls", type=int, default=100)
    args = parser.parse_args()
    if min(args.pairs, args.calls) < 1 or args.seconds <= 0:
        parser.error("pairs, calls and seconds must be positive")
    if not 0 <= args.hash_seed < 2**32:
        parser.error("hash-seed must fit an unsigned 32-bit integer")
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    if args.profile:
        if not args.package or (args.profile == "memray" and not args.output):
            parser.error("profiling requires a package, and Memray requires output")
        profile(args)
    elif args.package:
        print(json.dumps(worker(args)))
    else:
        if not args.baseline_package or not args.candidate_package or not args.output:
            parser.error("baseline-package, candidate-package and output are required")
        Path(args.output).write_text(json.dumps(compare(args), indent=2) + "\n")


if __name__ == "__main__":
    main()
