"""Compare numeric streams with complete-token fragment boundaries.

Event timings materialize event payloads and are not compared with jiter.
The matching comparison materializes every cumulative array prefix with both
JsonModemValues.snapshot() and jiter partial parsing. Prefix equality is checked
before timing. Jiter includes the work of building contiguous prefix bytes.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import timeit


WORKLOADS = ("small_integers", "wide_signed", "wide_unsigned", "floats", "mixed_numbers", "large_integers")
MODES = ("events", "byte_view_events", "values_prefixes", "jiter_prefixes")


def workloads():
    rng = random.Random(6901)
    return {
        "small_integers": list(range(-512, 512)),
        "wide_signed": [rng.randrange(-(2**63), 2**63) for _ in range(1024)],
        "wide_unsigned": [rng.randrange(2**63, 2**64) for _ in range(1024)],
        "floats": [i / 7 for i in range(1024)],
        "mixed_numbers": [rng.randrange(-(2**63), 2**64) if i % 2 else i / 7 for i in range(1024)],
        "large_integers": [rng.randrange(2**199, 2**200) for _ in range(1024)],
    }


def complete_chunks(values, target_size):
    chunks = []
    pending = bytearray(b"[")
    for index, value in enumerate(values):
        token = json.dumps(value).encode() + (b"]" if index + 1 == len(values) else b",")
        if len(pending) > 1 and len(pending) + len(token) > target_size:
            chunks.append(bytes(pending))
            pending.clear()
        pending.extend(token)
    if pending:
        chunks.append(bytes(pending))
    return chunks


def events(module, chunks, byte_views=False):
    parser = module.JsonModem(byte_views=byte_views)
    count = 0
    for chunk in chunks:
        for kind, _path, _value in parser.feed(chunk):
            count += kind == "number"
    for kind, _path, _value in parser.finish():
        count += kind == "number"
    return count


def values_prefixes(module, chunks):
    parser = module.JsonModemValues()
    count = 0
    for chunk in chunks:
        for _update in parser.feed(chunk):
            pass
        value = parser.view().snapshot()
        count += len(value)
    for _update in parser.finish():
        pass
    return count


def jiter_prefixes(module, chunks):
    pending = bytearray()
    count = 0
    for chunk in chunks:
        pending.extend(chunk)
        value = module.from_json(bytes(pending), partial_mode=True)
        count += len(value)
    return count


def verify_prefixes(module, reference, chunks):
    parser = module.JsonModemValues()
    pending = bytearray()
    count = 0
    for chunk in chunks:
        pending.extend(chunk)
        list(parser.feed(chunk))
        actual = parser.view().snapshot()
        expected = reference.from_json(bytes(pending), partial_mode=True)
        assert json.dumps(actual) == json.dumps(expected)
        count += len(actual)
    list(parser.finish())
    return count


def measure(function, seconds):
    timer = timeit.Timer(function)
    calls = 1
    while timer.timeit(calls) < seconds:
        calls *= 2
    samples = [elapsed * 1e9 / calls for elapsed in timer.repeat(3, calls)]
    return {"ns": statistics.median(samples), "calls": calls, "samples_ns": samples}


def worker(args):
    package = Path(args.package).resolve()
    sys.path.insert(0, str(package))
    import jiter
    import jsonmodem

    assert Path(jsonmodem.__file__).resolve().is_relative_to(package)
    assert Path(jsonmodem._native.__file__).resolve().is_relative_to(package)
    results = {}
    for name, values in workloads().items():
        if name not in args.workloads:
            continue
        chunks = complete_chunks(values, args.chunk_target)
        count = verify_prefixes(jsonmodem, jiter, chunks)
        functions = {
            "events": lambda: events(jsonmodem, chunks),
            "byte_view_events": lambda: events(jsonmodem, chunks, True),
            "values_prefixes": lambda: values_prefixes(jsonmodem, chunks),
            "jiter_prefixes": lambda: jiter_prefixes(jiter, chunks),
        }
        for mode, function in functions.items():
            assert function() == (len(values) if mode.endswith("events") else count)
        results[name] = {
            "document_bytes": sum(map(len, chunks)),
            "document_sha256": hashlib.sha256(b"".join(chunks)).hexdigest(),
            "chunks": len(chunks), "chunk_bytes_range": [min(map(len, chunks)), max(map(len, chunks))],
            "numeric_values": len(values), "prefix_values": count,
            "timings": {mode: measure(function, args.seconds) for mode, function in functions.items()},
        }
    return {"package": jsonmodem.__file__, "extension": jsonmodem._native.__file__,
            "python": platform.python_version(), "jiter": jiter.__version__,
            "hash_seed": os.environ.get("PYTHONHASHSEED"), "workloads": results}


def compare(args):
    packages = {"baseline": args.baseline_package, "candidate": args.candidate_package}
    runs = {name: [] for name in packages}
    seeds = [(args.hash_seed + pair) % (2**32) for pair in range(args.pairs)]
    for pair, seed in enumerate(seeds):
        order = list(packages) if pair % 2 == 0 else list(reversed(packages))
        environment = {**os.environ, "PYTHONHASHSEED": str(seed)}
        for name in order:
            command = [sys.executable, __file__, "--package", packages[name],
                       "--seconds", str(args.seconds), "--chunk-target", str(args.chunk_target),
                       "--workloads", *args.workloads]
            runs[name].append(json.loads(subprocess.check_output(command, text=True, env=environment)))
        print(f"Completed comparison {pair + 1} of {args.pairs}", flush=True)
    summary = {}
    for workload in args.workloads:
        samples = {package: [run["workloads"][workload] for run in records] for package, records in runs.items()}
        assert len({row["document_sha256"] for rows in samples.values() for row in rows}) == 1
        summary[workload] = {}
        for mode in MODES:
            times = {package: [row["timings"][mode]["ns"] for row in rows] for package, rows in samples.items()}
            paired = [new / old for old, new in zip(times["baseline"], times["candidate"])]
            summary[workload][mode] = {
                "ns": {package: statistics.median(values) for package, values in times.items()},
                "candidate_over_baseline": statistics.median(paired), "paired_ratios": paired,
                "ratio_range": [min(paired), max(paired)],
            }
            print(f"{workload} {mode}: candidate / baseline = {statistics.median(paired):.3f}", flush=True)
        summary[workload]["values_over_jiter"] = {
            package: statistics.median(row["timings"]["values_prefixes"]["ns"] / row["timings"]["jiter_prefixes"]["ns"]
                                       for row in rows) for package, rows in samples.items()
        }
    return {"cpu": min(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "pairs": args.pairs, "seconds": args.seconds, "hash_seeds": seeds,
            "chunk_target": args.chunk_target, "gc_disabled": True, "summary": summary, "runs": runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-package")
    parser.add_argument("--candidate-package")
    parser.add_argument("--package", help=argparse.SUPPRESS)
    parser.add_argument("--output")
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument("--hash-seed", type=int, default=1729)
    parser.add_argument("--seconds", type=float, default=0.03)
    parser.add_argument("--chunk-target", type=int, default=512)
    parser.add_argument("--workloads", nargs="+", choices=WORKLOADS, default=list(WORKLOADS))
    args = parser.parse_args()
    if min(args.pairs, args.chunk_target) < 1 or args.seconds <= 0:
        parser.error("pairs, chunk-target and seconds must be positive")
    if not 0 <= args.hash_seed < 2**32:
        parser.error("hash-seed must fit an unsigned 32-bit integer")
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
