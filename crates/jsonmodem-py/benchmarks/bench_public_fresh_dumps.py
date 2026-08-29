"""Compare one dumps call on newly prepared values with a reused-input control."""

import argparse
import datetime
import gc
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import time

# Python's safe-path mode omits the script directory from module lookup.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_public_corpus import (
    SOURCE_HASHES as CORPUS_SOURCE_HASHES,
    library_order,
    load_libraries,
    module_metadata,
    unique_cases,
    verify_builds,
)
from public_corpus import (
    MANIFEST,
    load_manifest,
    read_document,
    reject_constant,
    select_documents,
    sha256_file,
)


SOURCE_HASHES = {
    **CORPUS_SOURCE_HASHES,
    "fresh_dumps_runner_sha256": sha256_file(__file__),
}

# "Fresh" describes newly prepared values, not cold processor or interpreter caches.
CONDITIONS = ("fresh", "reused")


def prepare_value(raw):
    return json.loads(raw.decode("utf-8"), parse_constant=reject_constant)


def verify_output(encoded, input_bytes, expected):
    """Check the actual timed output without retaining a reference Python value."""
    if type(encoded) is not bytes:
        raise AssertionError("dumps must return bytes")
    checked = {
        "input_bytes": input_bytes,
        "output_bytes": len(encoded),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "work_bytes": len(encoded),
    }
    if checked != expected:
        raise AssertionError("timed output differs from correctness preflight")
    return checked


def measure(function, raw, condition, warmups, expected):
    """Own all prepared values; time one call, keeping its result for verification."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown input condition: {condition}")
    if warmups < 0:
        raise ValueError("warmups must be nonnegative")
    clock = time.perf_counter_ns
    argument = prepare_value(raw)
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        for _ in range(warmups):
            result = function(argument)
            del result
        if condition == "fresh" and warmups:
            # Assignment would retain the warmup value while preparing its replacement.
            del argument
            argument = prepare_value(raw)
        start = clock()
        result = function(argument)
        elapsed = clock() - start
        if elapsed <= 0:
            raise ValueError("performance clock did not advance during the timed call")
        checked = verify_output(result, len(raw), expected)
        del result, argument
    finally:
        if enabled:
            gc.enable()
        else:
            gc.disable()
    clock_info = time.get_clock_info("perf_counter")
    return {
        "latency_ns": elapsed,
        "timed_calls": 1,
        "warmup_calls": warmups,
        "preparation_count": 2 if condition == "fresh" and warmups else 1,
        "returned_bytes_destruction_timed": False,
        "verification": checked,
        "clock": {
            "implementation": clock_info.implementation,
            "resolution_ns": clock_info.resolution * 1e9,
            "monotonic": clock_info.monotonic,
            "adjustable": clock_info.adjustable,
        },
    }


def worker(payload):
    if payload["expected_sources"] != SOURCE_HASHES:
        raise ValueError("benchmark source changed; restart with a frozen runner")
    if sys.implementation.name != "cpython":
        raise ValueError("fresh/reused measurements require CPython's reference-counted input lifetime")
    if payload["cpu"] is not None:
        if not hasattr(os, "sched_setaffinity"):
            raise ValueError("--cpu requires OS CPU-affinity support")
        os.sched_setaffinity(0, {payload["cpu"]})
    library = payload["library"]
    sys.path[:0] = library["pythonpath"]
    module = importlib.import_module(library["module"])
    raw = read_document(payload["document"], payload["directory"])
    measurement = measure(
        module.dumps, raw, payload["condition"], payload["warmups"], payload["expected_check"],
    )
    metadata = module_metadata(library, module)
    if metadata != payload["expected_metadata"]:
        raise ValueError(f"{library['name']} build or environment changed after verification")
    return {"metadata": metadata, "measurement": measurement}


def child(library, payload, hash_seed, timeout):
    environment = dict(os.environ, PYTHONHASHSEED=str(hash_seed), PYTHONNOUSERSITE="1")
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [library["python"], str(Path(__file__).resolve()), "_worker"],
        input=json.dumps(dict(payload, library=library, expected_sources=SOURCE_HASHES)),
        text=True, capture_output=True, check=False, env=environment, timeout=timeout,
    )
    if completed.returncode:
        raise ValueError(
            f"{library['name']} {payload['condition']} worker exited {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def condition_order(conditions, repeat, library_count):
    # Avoid tying both order reversals to the parity of the same repeat.
    return list(conditions) if (repeat // library_count) % 2 == 0 else list(reversed(conditions))


def summarize(runs, active, checks, references, conditions):
    names = list(runs[0]["libraries"])
    cases = {}
    for case in active:
        cases[case] = dict(checks[case], conditions={})
        for condition in conditions:
            measurements = {}
            for name in names:
                values = [run["libraries"][name][case][condition]["latency_ns"] for run in runs]
                median = statistics.median(values)
                measurements[name] = {
                    "latency_ns": median,
                    "throughput_MB_s": checks[case]["work_bytes"] * 1000 / median,
                    "process_latencies_ns": values,
                    "minimum_process_ns": min(values),
                    "maximum_process_ns": max(values),
                }
            ratios = {}
            for reference in references:
                ratios[reference] = {
                    name: {
                        "latency_ratio": measurements[name]["latency_ns"] / measurements[reference]["latency_ns"],
                        "paired_ratios": [
                            left / right for left, right in zip(
                                measurements[name]["process_latencies_ns"],
                                measurements[reference]["process_latencies_ns"],
                            )
                        ],
                    }
                    for name in names if name != reference
                }
            cases[case]["conditions"][condition] = {"measurements": measurements, "ratios": ratios}
    geomeans = {}
    for condition in conditions:
        geomeans[condition] = {}
        for reference in references:
            geomeans[condition][reference] = {}
            for name in names:
                if name == reference:
                    continue
                values = [
                    row["conditions"][condition]["ratios"][reference][name]["latency_ratio"]
                    for row in cases.values()
                ]
                geomeans[condition][reference][name] = {
                    "case_count": len(values),
                    "latency_ratio": math.exp(statistics.fmean(math.log(value) for value in values)),
                    "faster_cases": sum(value < 1 for value in values),
                    "slower_cases": sum(value > 1 for value in values),
                }
    return {"cases": cases, "geomeans": geomeans}


def compare(args):
    manifest = load_manifest(args.manifest)
    documents = select_documents(manifest, args.cases)
    libraries = load_libraries(args.libraries)
    references = list(dict.fromkeys(args.reference))
    unknown = set(references) - {library["name"] for library in libraries}
    if unknown:
        raise ValueError(f"unknown reference libraries: {sorted(unknown)}")
    payload = {
        "documents": documents, "operations": ["dumps"],
        "directory": str(Path(args.directory).resolve()), "cpu": args.cpu,
    }
    verified = verify_builds(libraries, payload, references, args.timeout)
    checks = verified[references[0]]["cases"]
    active, aliases = unique_cases(documents, ["dumps"], checks)
    result = {
        "schema_version": 1,
        "benchmark": "public-corpus-fresh-dumps",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "manifest": {"name": manifest["name"], "sha256": sha256_file(args.manifest)},
        **SOURCE_HASHES,
        "documents": documents,
        "references": references,
        "libraries": {name: row["metadata"] for name, row in verified.items()},
        "verification": {name: row["cases"] for name, row in verified.items()},
        "active_cases": active,
        "duplicate_cases": aliases,
        "method": {
            "conditions": args.conditions,
            "processes": "Each library, document, condition, and repeat runs in a fresh interpreter process. Correctness preflight runs in separate processes.",
            "fresh": "Warm the library on a standard-library prepared value. Destroy that value before parsing the original bytes again. Time the replacement value's first serialization.",
            "reused": "Warm the library on a standard-library prepared value. Time one more serialization of that same value.",
            "zero_warmups": "Both conditions prepare once and time the first call. The fresh condition does not prepare a throwaway value when warmups are zero.",
            "preparation": "Only one parsed copy of the selected document exists when timing starts. Original bytes remain available for preparation; no reference Python value is retained in timed workers. All preparation is outside timing.",
            "latency": "Nanoseconds for one complete dumps call, including Python call and stopwatch overhead. Returned bytes remain alive when the clock stops; their destruction is excluded. Lower is better.",
            "throughput": "Decimal MB/s (1 MB = 1,000,000 bytes), using encoded output bytes. Higher is better.",
            "correctness": "Preflight checks exact values, types, float bits, dictionary order, input mutation, and encoded outputs. After timing, check the actual returned bytes' exact length and SHA-256 against preflight. Check runner, library, and interpreter fingerprints before accepting results.",
            "excludes": "Downloads, file reads, input hashes, preparation, warmups, output verification, result destruction, and metadata collection. No calibration or repeated timed calls on a value.",
            "gc": "Collect cyclic GC after initial preparation and disable it before warmups. Do not collect between warmups and timing. Restore its prior enabled state afterward. CPython reference counting releases the warmup value before replacement preparation.",
            "cache_limits": "These conditions measure newly prepared versus reused object behavior. Allocator and processor-cache history also differ, and the interpreter may share some immutable scalars. Results do not isolate UTF-8 caching or promise empty caches.",
            "ordering": "Rotate library order each repeat. Reverse condition order after each group of N repeats, where N is the number of libraries. Shuffle documents deterministically. Use one hash seed for all workers within a repeat.",
            "summary": "Per-case medians of single-call process latencies, with every process latency retained. Each condition is summarized separately; there is no combined-condition aggregate.",
            "geomean": "For each condition and unique document, divide a library's median process latency by the reference's median. Take the geometric mean with equal document weights. Lower is better; 1 means equal latency. Do not mix these results with the repeated-call suite, which includes output destruction.",
            "duplicates": "Deduplicate exact encoded outputs after complete correctness preflight. duplicate_cases lists omitted copies.",
            "timed_calls_per_process": 1,
            "warmup_calls": args.warmups,
            "returned_bytes_destruction_timed": False,
            "process_repeats": args.repeats,
            "requested_cpu": args.cpu,
        },
        "runs": [],
    }
    for repeat in range(args.repeats):
        order = library_order(libraries, repeat)
        conditions = condition_order(args.conditions, repeat, len(libraries))
        shuffled = list(documents)
        random.Random(1729 + repeat).shuffle(shuffled)
        run = {
            "repeat": repeat + 1, "python_hash_seed": 1729 + repeat,
            "library_order": [library["name"] for library in order],
            "condition_order": conditions,
            "document_order": [document["name"] for document in shuffled],
            "libraries": {library["name"]: {} for library in order},
        }
        for document in shuffled:
            case = "dumps:" + document["name"]
            if case not in active:
                continue
            for condition in conditions:
                for library in order:
                    name = library["name"]
                    response = child(library, {
                        "document": document, "condition": condition,
                        "directory": payload["directory"], "cpu": args.cpu,
                        "warmups": args.warmups, "expected_check": checks[case],
                        "expected_metadata": verified[name]["metadata"],
                    }, 1729 + repeat, args.timeout)
                    if response["metadata"] != verified[name]["metadata"]:
                        raise ValueError(f"{name} build or environment changed after verification")
                    measurement = response["measurement"]
                    if measurement["verification"] != checks[case]:
                        raise ValueError(f"{name} {case} {condition} output changed after verification")
                    run["libraries"][name].setdefault(case, {})[condition] = measurement
        result["runs"].append(run)
        print(f"Completed fresh/reused repeat {repeat + 1} of {args.repeats}", file=sys.stderr, flush=True)
    result["summary"] = summarize(result["runs"], active, checks, references, args.conditions)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--manifest", type=Path, default=MANIFEST)
    run.add_argument("--directory", type=Path, required=True)
    run.add_argument("--cases", nargs="+")
    run.add_argument("--libraries", type=Path, required=True)
    run.add_argument("--reference", action="append", required=True)
    run.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS))
    run.add_argument("--cpu", type=int)
    run.add_argument("--repeats", type=int, default=9, help="Fresh processes per library, document, and condition.")
    run.add_argument("--warmups", type=int, default=10, help="Untimed calls before the single timed call; zero skips throwaway preparation.")
    run.add_argument("--timeout", type=float, default=600, help="Maximum seconds for one worker.")
    run.add_argument("--output", type=Path, required=True)
    commands.add_parser("_worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.command == "_worker":
            print(json.dumps(worker(json.load(sys.stdin)), allow_nan=False))
            return
        if args.repeats < 1 or args.warmups < 0:
            parser.error("repeats must be positive; warmups must be nonnegative")
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            parser.error("timeout must be finite and positive")
        if args.cpu is not None and args.cpu < 0:
            parser.error("cpu must be nonnegative")
        if len(set(args.conditions)) != len(args.conditions):
            parser.error("conditions must not repeat")
        result = compare(args)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=args.output.parent,
                prefix="." + args.output.name + "-", suffix=".tmp", delete=False,
            ) as destination:
                temporary = Path(destination.name)
                json.dump(result, destination, indent=2, allow_nan=False)
                destination.write("\n")
            os.replace(temporary, args.output)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(f"{len(result['active_cases'])} unique dumps cases; result written to {args.output}")
    except (ImportError, OSError, ValueError, AssertionError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
