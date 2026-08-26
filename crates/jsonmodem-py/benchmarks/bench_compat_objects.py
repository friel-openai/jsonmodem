"""Alternating complete-call timings for options, objects, and optional NumPy."""

import argparse
import dataclasses
import json
import importlib.util
import os
import platform
from pathlib import Path

import jsonmodem
import numpy as np
import orjson

spec = importlib.util.spec_from_file_location("bench_orjson_compat", Path(__file__).with_name("bench_orjson_compat.py"))
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
measure = benchmark.measure


@dataclasses.dataclass
class Record:
    id: int
    name: str


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rounds", type=int, default=11)
    parser.add_argument("--seconds", type=float, default=0.1)
    parser.add_argument("--numpy-shapes", nargs="+", choices=("rows4", "flat", "rows100"), default=["rows4"])
    args = parser.parse_args()
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
    cases = [
        ("sorted_medium", [{"id": i, "score": i / 7, "name": f"item-{i}"} for i in range(1000)], 32),
        ("dataclasses_1000", [Record(i, f"item-{i}") for i in range(1000)], 0),
        ("non_str_keys", {i: str(i) for i in range(1000)}, 4),
    ]
    shapes = {"rows4": (25000, 4), "flat": (100000,), "rows100": (1000, 100)}
    for dtype in ("int64", "float32", "float64"):
        for shape in args.numpy_shapes:
            suffix = "" if shape == "rows4" else "_" + shape
            cases.append(("numpy_" + dtype + suffix, np.arange(100000, dtype=dtype).reshape(shapes[shape]), 16))
    results = {"python": platform.python_version(), "numpy": np.__version__,
               "orjson": orjson.__version__, "cpu": cpu, "rounds": args.rounds, "cases": []}
    for name, value, option in cases:
        ours = lambda obj: jsonmodem.dumps(obj, option=option)
        theirs = lambda obj: orjson.dumps(obj, option=option)
        assert ours(value) == theirs(value)
        result = measure(ours, theirs, value, args.rounds, args.seconds)
        result["name"] = name
        results["cases"].append(result)
        print(f"{name}: {result['jsonmodem_ns']:,.0f} ns / {result['orjson_ns']:,.0f} ns = {result['ratio']:.2f}x", flush=True)
    ours_value = [jsonmodem.Fragment(b'{"x":[1,2,3]}')] * 1000
    theirs_value = [orjson.Fragment(b'{"x":[1,2,3]}')] * 1000
    ours = lambda _: jsonmodem.dumps(ours_value)
    theirs = lambda _: orjson.dumps(theirs_value)
    assert ours(None) == theirs(None)
    result = measure(ours, theirs, None, args.rounds, args.seconds)
    result["name"] = "fragments_1000"
    results["cases"].append(result)
    print(f"fragments_1000: {result['ratio']:.2f}x", flush=True)
    with open(args.output, "w") as output:
        json.dump(results, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
