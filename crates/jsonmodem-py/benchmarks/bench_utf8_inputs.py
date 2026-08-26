"""Compare bytes with warmed Python str input on float and Unicode documents."""

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
        "profile_compat", Path(__file__).with_name("profile_compat.py")
    )
    profile_compat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile_compat)
    cases = {}
    for name in ("loads_floats", "loads_bmp"):
        _, document, _ = profile_compat.workload(jsonmodem, name)
        for kind, value in (("bytes", document), ("str", document.decode("utf-8"))):
            # This check also warms Python str's cached UTF-8 representation.
            assert jsonmodem.loads(value) == orjson.loads(value)
            cases[name + "_" + kind] = profile_compat.benchmark.measure(
                jsonmodem.loads, orjson.loads, value, 3, args.seconds
            )
    return {
        "package": jsonmodem.__file__, "extension": jsonmodem._native.__file__,
        "python": platform.python_version(), "orjson": orjson.__version__,
        "utf8_cache_warmed": True, "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package")
    parser.add_argument("--baseline-package")
    parser.add_argument("--candidate-package")
    parser.add_argument("--output")
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument("--seconds", type=float, default=0.06)
    parser.set_defaults(cases=None)
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
        bench_output_buffers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench_output_buffers)
        result = bench_output_buffers.compare(args, worker_script=__file__)
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
