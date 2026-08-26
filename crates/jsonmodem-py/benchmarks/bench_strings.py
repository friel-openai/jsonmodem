"""Compare two saved jsonmodem packages and orjson on synthetic string fixtures.

Each comparison runs both packages in separate processes, alternating which
runs first. Each process checks results, then records three measurements per
library with garbage collection disabled. Loop counts target --seconds in
the slower library, using bench_orjson_compat.measure.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys


def payloads():
    return {
        "short_plain": "plain",
        "short_escaped": "line\nquote\"",
        "plain_values": [f"string-{i}-abcdefghijklmnopqrstuvwxyz" for i in range(1000)],
        "escaped_values": [f"line-{i}\nquote\"slash\\" for i in range(1000)],
        "unicode_escapes": [f"snow-{i}\u2603\U0001f642" for i in range(1000)],
        "escaped_keys": [
            {"first\nkey": f"value-{i}\t", "second\"key": "\u2603\n"}
            for i in range(1000)
        ],
        "unique_keys": {f"key-{i}\n\"": f"value-{i}\t" for i in range(600)},
        "long_plain": "abcdefghijklmnopqrstuvwxyz0123456789" * 4096,
        "long_escaped": ("plain" * 12 + "\n\"\\\t") * 2048,
        "late_escape": "abcdefghijklmnopqrstuvwxyz0123456789" * 4096 + "\n",
        "medium": [
            {"id": i, "score": i / 7, "active": i % 3 == 0, "name": f"item-{i}"}
            for i in range(1000)
        ],
        "integers": list(range(-5000, 5000)),
    }


def worker(args):
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
    cases = {}
    for name, value in payloads().items():
        if args.cases and name not in args.cases:
            continue
        for operation in args.operations:
            document = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()
            inputs = [(kind, benchmark.LOAD_INPUTS[kind](document)) for kind in args.inputs]
            if operation == "dumps":
                inputs = [("object", value)]
            ours, theirs = getattr(jsonmodem, operation), getattr(orjson, operation)
            for kind, argument in inputs:
                assert ours(argument) == theirs(argument), (name, operation, kind)
                cases[f"{operation}/{name}/{kind}"] = benchmark.measure(
                    ours, theirs, argument, 3, args.seconds
                )
    return {
        "package": jsonmodem.__file__, "extension": jsonmodem._native.__file__,
        "python": platform.python_version(), "orjson": orjson.__version__, "cases": cases,
    }


def compare(args):
    packages = {"baseline": args.baseline_package, "candidate": args.candidate_package}
    runs = {name: [] for name in packages}
    for pair in range(args.pairs):
        order = list(packages) if pair % 2 == 0 else list(reversed(packages))
        environment = dict(os.environ, PYTHONHASHSEED=str(1729 + pair))
        for name in order:
            command = [sys.executable, __file__, "--package", packages[name],
                       "--seconds", str(args.seconds), "--operations", *args.operations,
                       "--inputs", *args.inputs]
            if args.cases:
                command.extend(["--cases", *args.cases])
            runs[name].append(json.loads(subprocess.check_output(command, text=True, env=environment)))
        print(f"Completed comparison {pair + 1} of {args.pairs}", flush=True)
    summary = {}
    for case in runs["baseline"][0]["cases"]:
        samples = {name: [run["cases"][case] for run in records] for name, records in runs.items()}
        paired = [new["jsonmodem_ns"] / old["jsonmodem_ns"]
                  for old, new in zip(samples["baseline"], samples["candidate"])]
        summary[case] = {
            "candidate_over_baseline": statistics.median(paired),
            "ratio_range": [min(paired), max(paired)], "paired_ratios": paired,
            "ns": {name: statistics.median(row["jsonmodem_ns"] for row in rows)
                   for name, rows in samples.items()},
            "orjson_ns": {name: statistics.median(row["orjson_ns"] for row in rows)
                          for name, rows in samples.items()},
            "over_orjson": {name: statistics.median(row["ratio"] for row in rows)
                            for name, rows in samples.items()},
        }
        print(f"{case}: candidate / baseline = {statistics.median(paired):.3f}", flush=True)
    return {
        "cpu": min(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "python_hash_seeds": list(range(1729, 1729 + args.pairs)),
        "pairs": args.pairs, "seconds": args.seconds, "summary": summary, "runs": runs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-package")
    parser.add_argument("--candidate-package")
    parser.add_argument("--package", help=argparse.SUPPRESS)
    parser.add_argument("--output")
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument("--seconds", type=float, default=0.03)
    parser.add_argument("--cases", nargs="+", choices=payloads())
    parser.add_argument("--operations", nargs="+", choices=("loads", "dumps"), default=["loads"])
    parser.add_argument("--inputs", nargs="+", choices=("bytes", "bytearray", "memoryview", "array_view"), default=["bytes"])
    args = parser.parse_args()
    if args.pairs < 1 or args.seconds <= 0:
        parser.error("pairs and seconds must be positive")
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    if args.package:
        print(json.dumps(worker(args)))
    else:
        if not args.baseline_package or not args.candidate_package or not args.output:
            parser.error("baseline-package, candidate-package and output are required")
        Path(args.output).write_text(json.dumps(compare(args), indent=2) + "\n")


if __name__ == "__main__":
    main()
