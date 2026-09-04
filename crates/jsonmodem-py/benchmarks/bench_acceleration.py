"""Measure optional encoding work, cache misses and output-size boundaries.

Times are nanoseconds per complete dumps call; lower is better. Fixture
construction and exact-output checks are outside timing. Run each package in
a fresh process and alternate package order when comparing implementations.
"""

import argparse
import dataclasses
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys


@dataclasses.dataclass
class Record:
    """Small rich object used before and after a primitive output prefix."""

    value: int


def workloads():
    start = datetime.datetime(2024, 2, 29, 3, 4, 5, 123456)
    cases = []
    for owners in (1, 2, 8, 9, 64):
        zones = [datetime.timezone(datetime.timedelta(minutes=i + 1), f"zone-{i}")
                 for i in range(owners)]
        for count in ((1, 16, 1024) if owners == 1 else (16, 1024)):
            value = [start.replace(tzinfo=zones[i % owners]) for i in range(count)]
            cases.append((f"offsets_{owners}_owners_{count}_dates", value, {}))
    cases.extend([
        ("datetime_scalar", start.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=1))), {}),
        ("datetime_naive", [start] * 1024, {}),
        ("datetime_utc", [start.replace(tzinfo=datetime.timezone.utc)] * 1024, {}),
        ("scalar_integer", 123456789, {}),
        ("tiny_list", [1, 2, 3], {}),
        ("tiny_dict", {"x": 1, "y": True}, {}),
        ("large_integers", list(range(-5000, 5000)), {}),
        ("repeated_keys", [{"repeated": i, "other": False} for i in range(1024)], {}),
        ("early_dataclass", [Record(7), "x" * 1024], {}),
        ("late_dataclass", ["x" * 1024, Record(7)], {}),
        ("early_default", [object(), "x" * 1024], {"default": lambda _: None}),
        ("late_default", ["x" * 1024, object()], {"default": lambda _: None}),
    ])
    for size in (255, 256, 257, 511, 512, 513, 1023, 1024, 1025, 16384):
        # JSON list punctuation adds four bytes to this single string.
        cases.append((f"output_{size}_bytes", ["x" * (size - 4)], {}))
    assert len(cases) == len({name for name, _, _ in cases})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--seconds", type=float, default=0.03)
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args()
    if args.seconds <= 0 or sys.flags.optimize:
        parser.error("Use positive seconds and keep assertions enabled")
    package = args.package.resolve(strict=True)
    sys.path.insert(0, str(package))
    import jsonmodem
    import orjson

    assert Path(jsonmodem.__file__).resolve().is_relative_to(package)
    assert Path(jsonmodem._native.__file__).resolve().is_relative_to(package)
    dumps = jsonmodem.dumps
    if args.portable:
        from jsonmodem.portable import dumps
    helper_path = Path(__file__).with_name("bench_orjson_compat.py")
    spec = importlib.util.spec_from_file_location("bench_orjson_compat", helper_path)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    cases = workloads()
    if args.cases and set(args.cases) - {name for name, _, _ in cases}:
        parser.error("Unknown case")
    results = {}
    for name, value, kwargs in cases:
        if args.cases and name not in args.cases:
            continue
        ours = lambda value: dumps(value, **kwargs)
        theirs = lambda value: orjson.dumps(value, **kwargs)
        output = ours(value)
        assert type(output) is bytes and output == theirs(value), name
        result = benchmark.measure(ours, theirs, value, 3, args.seconds)
        assert ours(value) == output and theirs(value) == output, name
        result.update(output_bytes=len(output), output_sha256=hashlib.sha256(output).hexdigest())
        results[name] = result
    print(json.dumps({
        "python": platform.python_version(), "orjson": orjson.__version__,
        "package": str(package), "portable": args.portable,
        "package_sha256": {str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in sorted(package.rglob("*"))
                           if path.is_file() and path.suffix in (".py", ".so")},
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "helper_sha256": hashlib.sha256(helper_path.read_bytes()).hexdigest(),
        "cases": results,
    }, allow_nan=False))


if __name__ == "__main__":
    main()
