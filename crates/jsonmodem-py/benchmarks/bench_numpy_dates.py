"""Compare complete NumPy timestamp serialization calls with orjson.

All timings are nanoseconds per call; lower is better. Array construction,
correctness checks, and file hashing are outside the timed operation. The
28 generated cases supplement, rather than replace, document benchmarks.
"""

import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import sys


def workloads(np):
    """Return fixed, valid timestamps with scalar, array, and option variants."""
    index = np.arange(4096, dtype=np.int64)
    values = {
        "Y": 30 + index % 60,
        "M": 360 + (index * 17) % 720,
        "D": 10_957 + (index * 137) % 21_915,
        "s": 946_684_800 + index * 7_919,
        "us": 946_684_800_123_456 + index * 7_919_123_456,
        "ns": 946_684_800_123_456_789 + index * 7_919_123_456_789,
    }
    arrays = {unit: raw.view(f"datetime64[{unit}]") for unit, raw in values.items()}
    cases = []
    for unit, array in arrays.items():
        for size, value in (("scalar", array[0]), ("16", array[:16]), ("4096", array)):
            cases.append((f"datetime_{unit}_{size}", value, {"option": 16}))
    for name, flags in (
        ("naive_utc", 2),
        ("omit_microseconds", 8),
        ("utc_z", 128),
        ("naive_utc_omit_microseconds", 2 | 8),
        ("naive_utc_z", 2 | 128),
        ("omit_microseconds_utc_z", 8 | 128),
        ("naive_utc_omit_microseconds_utc_z", 2 | 8 | 128),
    ):
        cases.append((f"datetime_us_4096_{name}", arrays["us"], {"option": 16 | flags}))
    cases.extend((
        ("datetime_us_empty", arrays["us"][:0], {"option": 16}),
        ("datetime_us_matrix", arrays["us"].reshape(64, 64), {"option": 16}),
        ("datetime_us_under_dict", {"dates": arrays["us"]}, {"option": 16}),
    ))
    assert len(cases) == 28 and len({name for name, _, _ in cases}) == 28
    return cases


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    directory = Path(__file__).resolve().parent
    return {name: sha256(directory / name) for name in (
        "bench_numpy_dates.py", "bench_orjson_compat.py", "bench_output_buffers.py",
    )}


def worker(args):
    if sys.flags.optimize:
        raise ValueError("run without -O so correctness checks remain enabled")
    # Load the reference and NumPy before adding a candidate package directory,
    # which may itself be a virtual environment containing different versions.
    import numpy as np
    import orjson

    before = sources()
    package = Path(args.package).resolve()
    sys.path.insert(0, str(package))
    try:
        jsonmodem = importlib.import_module("jsonmodem")
    finally:
        removed = sys.path.pop(0)
        if removed != str(package):
            raise ValueError("candidate import changed the package search order")
    assert Path(jsonmodem.__file__).resolve().is_relative_to(package)
    assert Path(jsonmodem._native.__file__).resolve().is_relative_to(package)
    extension = Path(jsonmodem._native.__file__).resolve()
    native_hash = sha256(extension)
    reference = Path(orjson.orjson.__file__).resolve()
    reference_hash = sha256(reference)
    cases = workloads(np)
    if args.cases:
        unknown = set(args.cases) - {name for name, _, _ in cases}
        if unknown:
            raise ValueError(f"unknown cases: {sorted(unknown)}")
        cases = [case for case in cases if case[0] in args.cases]
    results = {}
    if not args.check_only:
        from bench_orjson_compat import measure

    for name, value, kwargs in cases:
        ours = lambda obj: jsonmodem.dumps(obj, **kwargs)
        theirs = lambda obj: orjson.dumps(obj, **kwargs)
        output = ours(value)
        assert output == theirs(value), name
        array = value["dates"] if isinstance(value, dict) else value
        metadata = {
            "dtype": str(array.dtype),
            "shape": list(array.shape),
            "input_bytes": int(array.nbytes),
            "input_sha256": hashlib.sha256(array.tobytes()).hexdigest(),
            "option": kwargs["option"],
            "output_bytes": len(output),
            "output_sha256": hashlib.sha256(output).hexdigest(),
        }
        if not args.check_only:
            metadata.update(measure(ours, theirs, value, 3, args.seconds))
        results[name] = metadata
    assert sources() == before
    assert sha256(extension) == native_hash
    assert sha256(reference) == reference_hash
    return {
        "timing": not args.check_only,
        "latency_units": "nanoseconds per complete dumps call; lower is better",
        "package": jsonmodem.__file__,
        "extension": str(extension),
        "extension_sha256": native_hash,
        "jsonmodem": jsonmodem.__version__,
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "python_executable_sha256": sha256(sys.executable),
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "orjson": orjson.__version__,
        "orjson_extension": str(reference),
        "orjson_extension_sha256": reference_hash,
        "numpy": np.__version__,
        "source_sha256": before,
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-package")
    parser.add_argument("--candidate-package")
    parser.add_argument("--package", help="Check or measure one package directory")
    parser.add_argument("--check-only", action="store_true", help="Check all outputs without timing")
    parser.add_argument("--output")
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument("--seconds", type=float, default=0.03)
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args()
    if sys.flags.optimize:
        parser.error("run without -O so correctness checks remain enabled")
    if args.pairs < 1 or not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("pairs and seconds must be positive")
    if args.check_only and not args.package:
        parser.error("check-only requires package")
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    if args.package:
        print(json.dumps(worker(args), allow_nan=False))
        return
    if not args.baseline_package or not args.candidate_package or not args.output:
        parser.error("baseline-package, candidate-package and output are required")
    from bench_output_buffers import compare

    with Path(args.output).open("x") as stream:
        result = compare(args, worker_script=str(Path(__file__).resolve()))
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
