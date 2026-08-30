"""Compare complete date and time serialization calls with orjson.

Times are nanoseconds per call; lower is better. These generated Python values
supplement document benchmarks. Construction, correctness checks and file
hashing are excluded from timing. Known reference output differences are
recorded explicitly and must be excluded from equivalent-output scores.
"""

import argparse
import dataclasses
import datetime
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import sys
import uuid


REFERENCE_TIME_PADDING_CASES = frozenset(("time_16", "time_1024", "dates_under_dict"))


@dataclasses.dataclass
class Record:
    """An ordinary record containing either a timestamp or a control value."""

    index: int
    value: object


class DateTimeSubclass(datetime.datetime):
    """A subclass which must continue to use the supplied default callback."""


def isoformat(value):
    return value.isoformat()


def workloads():
    """Keep date types, options, fallback types and ordinary controls together."""
    start = datetime.datetime(2001, 1, 2, 3, 4, 5)
    naive = [
        start + datetime.timedelta(seconds=index * 7919, microseconds=(123456 + index * 65537) % 1000000)
        for index in range(1024)
    ]
    utc = [value.replace(tzinfo=datetime.timezone.utc) for value in naive]
    positive = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    fixed = [value.replace(tzinfo=positive) for value in naive]
    dates = [value.date() for value in naive]
    times = [value.time() for value in naive]
    cases = []
    for name, values in (
        ("datetime_naive", naive), ("datetime_utc", utc),
        ("datetime_fixed_offset", fixed), ("date", dates), ("time", times),
    ):
        for size, value in (("scalar", values[0]), ("16", values[:16]), ("1024", values)):
            cases.append((f"{name}_{size}", value, {}))
    for name, values in (("datetime_naive", naive), ("datetime_utc", utc), ("time", times)):
        cases.append((f"{name}_1024_zero_microseconds", [value.replace(microsecond=0) for value in values], {}))
    for name, flags in (
        ("naive_utc", 2), ("omit_microseconds", 8), ("utc_z", 128),
        ("naive_utc_omit_microseconds", 2 | 8), ("naive_utc_z", 2 | 128),
        ("omit_microseconds_utc_z", 8 | 128), ("naive_utc_omit_microseconds_utc_z", 2 | 8 | 128),
    ):
        cases.append((f"datetime_naive_1024_{name}", naive, {"option": flags}))
    for name, flags in (("omit_microseconds", 8), ("utc_z", 128), ("omit_microseconds_utc_z", 8 | 128)):
        cases.append((f"datetime_utc_1024_{name}", utc, {"option": flags}))
    cases.extend((
        ("time_1024_omit_microseconds", times, {"option": 8}),
        ("date_1024_options", dates, {"option": 2 | 8 | 128}),
        ("dates_under_dict", {"date": dates, "time": times, "datetime": utc}, {}),
        ("dataclass_dates", [Record(index, value) for index, value in enumerate(utc)], {}),
        ("datetime_passthrough", naive, {"option": 512, "default": isoformat}),
        ("datetime_subclass", [DateTimeSubclass(2001, 1, 2, 3, 4, 5, index) for index in range(1024)], {"default": isoformat}),
    ))
    for name, offset in (
        ("named_zero", datetime.timezone(datetime.timedelta(0), "zero")),
        ("negative", datetime.timezone(datetime.timedelta(hours=-3, minutes=-30))),
        ("seconds", datetime.timezone(datetime.timedelta(hours=5, minutes=30, seconds=45))),
    ):
        cases.append((f"datetime_{name}_offset_1024", [value.replace(tzinfo=offset) for value in naive], {}))
    cases.extend((
        ("uuid_scalar_control", uuid.UUID(int=123456789), {}),
        ("uuid_list_control", [uuid.UUID(int=(index + 1) * 65537) for index in range(1024)], {}),
        ("dict_control", {"id": 123, "name": "record", "active": True}, {}),
        ("list_control", list(range(1024)), {}),
        ("string_control", "ordinary text", {}),
        ("dataclass_control", [Record(index, "ordinary text") for index in range(1024)], {}),
    ))
    assert len(cases) == len({name for name, _, _ in cases}) == 43
    return cases


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    directory = Path(__file__).resolve().parent
    return {name: sha256(directory / name) for name in (
        "bench_datetime.py", "bench_orjson_compat.py", "bench_output_buffers.py",
    )}


def _load_helper(name):
    """Load a known adjacent helper without adding the working directory to sys.path."""
    spec = importlib.util.spec_from_file_location("_datetime_" + name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def time_padding_outputs(value):
    """Distinguish correct time fractions from orjson 3.11.9's missing zero."""
    def normalized(item, reference):
        if type(item) is datetime.time:
            if reference and 10000 <= item.microsecond <= 99999:
                return item.isoformat(timespec="seconds") + "." + str(item.microsecond)
            return item.isoformat()
        if type(item) in (datetime.date, datetime.datetime):
            return item.isoformat()
        if type(item) is list:
            return [normalized(child, reference) for child in item]
        if type(item) is dict:
            return {key: normalized(child, reference) for key, child in item.items()}
        raise TypeError("unexpected time-padding fixture type")

    return tuple(json.dumps(normalized(value, reference), separators=(",", ":")).encode("utf-8")
                 for reference in (False, True))


def check_outputs(name, value, kwargs, output, reference, version):
    assert type(output) is bytes and type(reference) is bytes, name
    if version == "3.11.9" and name in REFERENCE_TIME_PADDING_CASES:
        assert not kwargs, name
        expected, reference_expected = time_padding_outputs(value)
        assert output == expected and reference == reference_expected and expected != reference_expected, name
    else:
        assert output == reference, name


def fixture_metadata(value, kwargs, output, reference=None):
    if reference is None:
        reference = output
    return {
        "input_repr_sha256": hashlib.sha256(repr(value).encode("utf-8")).hexdigest(),
        "root_type": type(value).__module__ + "." + type(value).__qualname__,
        "option": kwargs.get("option", 0),
        "default": kwargs["default"].__name__ if "default" in kwargs else None,
        "output_bytes": len(output), "output_sha256": hashlib.sha256(output).hexdigest(),
        "reference_exact_match": output == reference,
        "reference_output_bytes": len(reference), "reference_output_sha256": hashlib.sha256(reference).hexdigest(),
    }


def worker(args):
    if sys.flags.optimize:
        raise ValueError("run without -O so correctness checks remain enabled")
    import orjson

    before = sources()
    package = Path(args.package).resolve()
    sys.path.insert(0, str(package))
    try:
        jsonmodem = importlib.import_module("jsonmodem")
    finally:
        if sys.path.pop(0) != str(package):
            raise ValueError("candidate import changed the package search order")
    assert Path(jsonmodem.__file__).resolve().is_relative_to(package)
    assert jsonmodem.dumps is jsonmodem._native.dumps
    extension = Path(jsonmodem._native.__file__).resolve()
    assert extension.is_relative_to(package)
    native_hash = sha256(extension)
    package_sources = {name: sha256(package / "jsonmodem" / name) for name in (
        "__init__.py", "_compat.py", "_numpy.py",
    )}
    reference = Path(orjson.orjson.__file__).resolve()
    reference_hash = sha256(reference)
    reference_source = Path(orjson.__file__).resolve()
    reference_source_hash = sha256(reference_source)
    assert orjson.dumps is orjson.orjson.dumps
    cases = workloads()
    if args.cases:
        unknown = set(args.cases) - {name for name, _, _ in cases}
        if unknown:
            raise ValueError(f"unknown cases: {sorted(unknown)}")
        cases = [case for case in cases if case[0] in args.cases]
    results = {}
    if not args.check_only:
        measure = _load_helper("bench_orjson_compat").measure

    for name, value, kwargs in cases:
        ours = lambda obj: jsonmodem.dumps(obj, **kwargs)
        theirs = lambda obj: orjson.dumps(obj, **kwargs)
        output = ours(value)
        reference_output = theirs(value)
        check_outputs(name, value, kwargs, output, reference_output, orjson.__version__)
        metadata = fixture_metadata(value, kwargs, output, reference_output)
        timing = measure(ours, theirs, value, 3, args.seconds) if not args.check_only else {}
        after = ours(value)
        reference_after = theirs(value)
        check_outputs(name, value, kwargs, after, reference_after, orjson.__version__)
        assert after == output and reference_after == reference_output, name
        assert fixture_metadata(value, kwargs, after, reference_after) == metadata, name
        metadata.update(timing)
        results[name] = metadata
    assert sources() == before and sha256(extension) == native_hash and sha256(reference) == reference_hash
    assert package_sources == {name: sha256(package / "jsonmodem" / name) for name in package_sources}
    assert sha256(reference_source) == reference_source_hash
    return {
        "timing": not args.check_only,
        "latency_units": "nanoseconds per complete dumps call; lower is better",
        "package": jsonmodem.__file__, "extension": str(extension), "extension_sha256": native_hash,
        "package_source_sha256": package_sources,
        "jsonmodem": jsonmodem.__version__, "python": platform.python_version(),
        "python_executable": sys.executable, "python_executable_sha256": sha256(sys.executable),
        "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
        "python_safe_path": sys.flags.safe_path, "python_isolated": sys.flags.isolated,
        "python_no_user_site": sys.flags.no_user_site,
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "orjson": orjson.__version__, "orjson_extension": str(reference), "orjson_extension_sha256": reference_hash,
        "orjson_source": str(reference_source), "orjson_source_sha256": reference_source_hash,
        "source_sha256": before, "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-package")
    parser.add_argument("--candidate-package")
    parser.add_argument("--package", help="Check or measure one package directory")
    parser.add_argument("--check-only", action="store_true", help="Check outputs without timing")
    parser.add_argument("--output")
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--seconds", type=float, default=0.04)
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
    compare = _load_helper("bench_output_buffers").compare

    with Path(args.output).open("x") as stream:
        result = compare(args, worker_script=str(Path(__file__).resolve()))
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
