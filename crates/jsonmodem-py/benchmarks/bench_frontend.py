"""Compare complete-document decoding and string output, not streaming APIs."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

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

    cases = []
    for name, value in benchmark.PAYLOADS.items():
        document = orjson.dumps(value)
        for kind, convert in benchmark.LOAD_INPUTS.items():
            suffix = "" if kind == "bytes" else "_" + kind
            cases.append(("loads_" + name + suffix, "loads", convert(document), {}))

    long = "x" * 131072
    strings = [
        ("empty", ""),
        ("tiny", "hello"),
        ("below_threshold", "x" * 255),
        ("at_threshold", "x" * 256),
        ("medium", "x" * 4096),
        ("long", long),
        ("early_quote", '"' + long),
        ("late_quote", long + '"'),
        ("dense_escapes", "\n\\\"\x00" * 8192),
        ("latin1", "\u00e9" * 65536),
        ("bmp", "\u2603" * 43690),
        ("non_bmp", "\U0001f600" * 32768),
    ]
    for name, value in strings:
        cases.append(("dumps_root_" + name, "dumps", value, {}))
        cases.append(("loads_root_" + name, "loads", orjson.dumps(value), {}))
    cases.extend([
        ("dumps_root_append_newline", "dumps", long, {"option": 1024}),
        ("dumps_root_indent", "dumps", long, {"option": 1}),
        ("loads_escaped_values", "loads", orjson.dumps(["line\nvalue\\tail"] * 1000), {}),
        ("loads_unicode_escapes", "loads", json.dumps(["\u2603\U0001f600"] * 1000).encode(), {}),
        ("loads_repeated_escaped_keys", "loads", orjson.dumps([{"key\n": i} for i in range(1000)]), {}),
        ("loads_unique_escaped_keys", "loads", orjson.dumps({f"key\n{i}": i for i in range(600)}), {}),
    ])
    if args.cases:
        unknown = set(args.cases) - {name for name, _, _, _ in cases}
        if unknown:
            raise ValueError(f"unknown cases: {sorted(unknown)}")
    results = {}
    for name, operation, value, kwargs in cases:
        if args.cases and name not in args.cases:
            continue
        ours_function, theirs_function = getattr(jsonmodem, operation), getattr(orjson, operation)
        ours = lambda obj: ours_function(obj, **kwargs)
        theirs = lambda obj: theirs_function(obj, **kwargs)
        assert ours(value) == theirs(value), name
        results[name] = benchmark.measure(ours, theirs, value, 3, args.seconds)
    return {"package": jsonmodem.__file__, "extension": jsonmodem._native.__file__,
            "python": platform.python_version(), "orjson": orjson.__version__,
            "cases": results}


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
        spec = importlib.util.spec_from_file_location(
            "bench_output_buffers", Path(__file__).with_name("bench_output_buffers.py")
        )
        comparison = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = comparison
        spec.loader.exec_module(comparison)
        result = comparison.compare(args, __file__)
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
