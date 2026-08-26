"""Compare two jsonmodem packages with orjson in alternating child processes."""

import argparse
import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys


@dataclasses.dataclass
class Record:
    """Synthetic dataclass used to check the fallback serializer's overhead."""

    id: int
    name: str


@dataclasses.dataclass
class SlotsRecord:
    """Equivalent declared fields stored in slots instead of an instance dictionary."""

    __slots__ = ("id", "name")
    id: int
    name: str


@dataclasses.dataclass
class NestedRecord:
    """A record with a child dataclass and an ordinary dictionary."""

    id: int
    child: Record
    attributes: dict


def worker(args):
    package = Path(args.package).resolve()
    sys.path.insert(0, str(package))
    import jsonmodem
    import numpy as np
    import orjson

    assert Path(jsonmodem.__file__).resolve().is_relative_to(package)
    assert Path(jsonmodem._native.__file__).resolve().is_relative_to(package)

    spec = importlib.util.spec_from_file_location(
        "bench_orjson_compat", Path(__file__).with_name("bench_orjson_compat.py")
    )
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    cases = [(name, value, {}) for name, value in benchmark.PAYLOADS.items()]
    rng = random.Random(1729)
    cases.extend([
        ("integers_wide_signed", [rng.randrange(-(1 << 63), 1 << 63) for _ in range(10000)], {}),
        ("integers_wide_unsigned", [rng.randrange(1 << 63, 1 << 64) for _ in range(10000)], {}),
        ("scalar_integer", 123456789, {}),
        ("integers_tiny", [0, -1, 10, -100, 999], {}),
        ("indent_integers", benchmark.PAYLOADS["integers"], {"option": 1}),
        ("strict_integers", benchmark.PAYLOADS["integers"], {"option": 64}),
        ("sorted_medium", benchmark.PAYLOADS["medium"], {"option": 32}),
        ("integer_keys", {i: str(i) for i in range(1000)}, {"option": 4}),
        ("dataclasses", [Record(i, f"item-{i}") for i in range(1000)], {}),
        ("dataclass_single", Record(123, "record"), {}),
        ("dataclass_slots_single", SlotsRecord(123, "record"), {}),
        ("dataclass_slots", [SlotsRecord(i, f"item-{i}") for i in range(1000)], {}),
        ("dataclass_nested", [NestedRecord(i, Record(i + 1, f"child-{i}"), {"z": i, "a": i + 1}) for i in range(1000)], {}),
        ("dataclass_indent", [Record(i, f"item-{i}") for i in range(1000)], {"option": 1}),
        ("dataclass_sorted", [NestedRecord(i, Record(i + 1, f"child-{i}"), {"z": i, "a": i + 1}) for i in range(1000)], {"option": 32}),
        ("dataclass_default", [Record(i, object()) for i in range(1000)], {"default": lambda _: "converted"}),
        ("numpy_int64", np.arange(100000, dtype=np.int64).reshape(25000, 4), {"option": 16}),
        ("numpy_float32", np.arange(100000, dtype=np.float32).reshape(25000, 4), {"option": 16}),
        ("late_default", ["x" * 256] * 100 + [object()], {"default": lambda _: None}),
    ])
    for count in (8, 16):
        record_type = dataclasses.make_dataclass(
            "Fields" + str(count), [("field_" + str(i), int) for i in range(count)]
        )
        cases.append((
            "dataclass_fields" + str(count),
            [record_type(*range(i, i + count)) for i in range(1000)],
            {},
        ))
    if args.cases:
        unknown = set(args.cases) - {name for name, _, _ in cases}
        if unknown:
            raise ValueError(f"unknown cases: {sorted(unknown)}")
    results = {}
    for name, value, kwargs in cases:
        if args.cases and name not in args.cases:
            continue
        ours = lambda obj: jsonmodem.dumps(obj, **kwargs)
        theirs = lambda obj: orjson.dumps(obj, **kwargs)
        assert ours(value) == theirs(value), name
        results[name] = benchmark.measure(ours, theirs, value, 3, args.seconds)
    return {"package": jsonmodem.__file__, "extension": jsonmodem._native.__file__,
            "python": platform.python_version(), "orjson": orjson.__version__,
            "numpy": np.__version__, "cases": results}


def compare(args, worker_script=__file__):
    packages = {"baseline": args.baseline_package, "candidate": args.candidate_package}
    runs = {name: [] for name in packages}
    for pair in range(args.pairs):
        order = list(packages) if pair % 2 == 0 else list(reversed(packages))
        environment = dict(os.environ, PYTHONHASHSEED=str(1729 + pair))
        for name in order:
            command = [sys.executable, worker_script, "--package", packages[name],
                       "--seconds", str(args.seconds)]
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
            "ratio_range": [min(paired), max(paired)],
            "paired_ratios": paired,
            "ns": {name: statistics.median(row["jsonmodem_ns"] for row in rows)
                   for name, rows in samples.items()},
            "orjson_ns": {name: statistics.median(row["orjson_ns"] for row in rows)
                          for name, rows in samples.items()},
            "over_orjson": {name: statistics.median(row["ratio"] for row in rows)
                            for name, rows in samples.items()},
        }
        print(f"{case}: candidate / baseline = {statistics.median(paired):.3f}", flush=True)
    return {"cpu": min(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "pairs": args.pairs, "seconds": args.seconds,
            "python_hash_seeds": list(range(1729, 1729 + args.pairs)),
            "summary": summary, "runs": runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-package")
    parser.add_argument("--candidate-package")
    parser.add_argument("--package", help=argparse.SUPPRESS)
    parser.add_argument("--output")
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument("--seconds", type=float, default=0.03)
    parser.add_argument("--cases", nargs="+")
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
