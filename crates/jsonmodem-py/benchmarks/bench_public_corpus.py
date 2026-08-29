"""Measure complete Python loads/dumps on hash-verified public JSON documents."""

import argparse
import datetime
import gc
import hashlib
import importlib
import importlib.machinery
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time

# Python's safe-path mode omits the script directory from module lookup.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from public_corpus import (
    MANIFEST,
    NAME,
    SHA256,
    assert_same,
    fetch_document,
    load_manifest,
    prepare_document,
    reject_constant,
    select_documents,
    sha256_file,
)


# Workers must use the same benchmark code that the coordinating process loaded.
SOURCE_HASHES = {
    "runner_sha256": sha256_file(__file__),
    "corpus_helper_sha256": sha256_file(Path(__file__).with_name("public_corpus.py")),
}


def load_libraries(path):
    """Read local build locations; those locations never enter result JSON."""
    path = Path(path).resolve()
    config = json.loads(path.read_bytes())
    if not isinstance(config, dict):
        raise ValueError("library configuration must be an object")
    libraries = config.get("libraries")
    if not isinstance(libraries, list) or not libraries:
        raise ValueError("library configuration needs a nonempty libraries list")
    names = set()
    for library in libraries:
        if not isinstance(library, dict):
            raise ValueError("libraries must be objects")
        unknown = set(library) - {
            "name", "module", "python", "pythonpath", "expected_version", "revision", "wheel_sha256",
        }
        if unknown:
            raise ValueError(f"unknown library configuration fields: {sorted(unknown)}")
        name = library.get("name", "")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            raise ValueError(f"invalid or duplicate library name: {name!r}")
        names.add(name)
        module = library.get("module", "")
        if not isinstance(module, str) or not all(part.isidentifier() for part in module.split(".")):
            raise ValueError(f"invalid module for {name}")
        if not isinstance(library.get("expected_version"), str):
            raise ValueError(f"expected_version is required for {name}")
        interpreter = Path(library.get("python", sys.executable))
        if not interpreter.is_absolute():
            interpreter = path.parent / interpreter
        if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
            raise ValueError(f"Python interpreter is not executable for {name}")
        # Keep a virtual environment's symlink: resolving it selects the base Python.
        library["python"] = str(interpreter.absolute())
        search = library.get("pythonpath", [])
        if not isinstance(search, list) or not all(isinstance(entry, str) for entry in search):
            raise ValueError(f"pythonpath must be a list of directories for {name}")
        library["pythonpath"] = [
            str((path.parent / entry).resolve()) for entry in search
        ]
        if any(not Path(entry).is_dir() for entry in library["pythonpath"]):
            raise ValueError(f"pythonpath directory does not exist for {name}")
        digest = library.get("wheel_sha256")
        if digest is not None and (not isinstance(digest, str) or not SHA256.fullmatch(digest)):
            raise ValueError(f"invalid wheel_sha256 for {name}")
        revision = library.get("revision")
        if revision is not None and (
            not isinstance(revision, str) or len(revision) != 40
            or any(character not in "0123456789abcdef" for character in revision)
        ):
            raise ValueError(f"revision must be a full Git commit ID for {name}")
    return libraries


def module_metadata(library, module):
    version = getattr(module, "__version__", None)
    if version != library["expected_version"]:
        raise ValueError(
            f"{library['name']} version is {version!r}, expected {library['expected_version']!r}"
        )
    source = Path(module.__file__).resolve()
    if library["pythonpath"] and not any(
        source.is_relative_to(Path(entry)) for entry in library["pythonpath"]
    ):
        raise ValueError(f"{library['name']} was not imported from its configured pythonpath")
    suffixes = (".py", *importlib.machinery.EXTENSION_SUFFIXES)
    if source.name == "__init__.py":
        files = sorted(path for path in source.parent.rglob("*") if path.name.endswith(suffixes))
        root = source.parent
    else:
        files, root = [source], source.parent
    metadata = {
        "module": library["module"],
        "version": version,
        "files": [
            {"name": str(path.relative_to(root)), "sha256": sha256_file(path)}
            for path in files
        ],
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "python_compiler": platform.python_compiler(),
        "python_cache_tag": sys.implementation.cache_tag,
        "executable_sha256": sha256_file(sys.executable),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "pointer_bits": 64 if sys.maxsize > 2**32 else 32,
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "python_malloc": os.environ.get("PYTHONMALLOC", "default"),
    }
    for key in ("revision", "wheel_sha256"):
        if key in library:
            metadata["declared_" + key] = library[key]
    return metadata


def verify_operation(module, operation, raw, value):
    if operation == "loads":
        assert_same(module.loads(raw), value)
        return {"input_bytes": len(raw), "work_bytes": len(raw)}
    encoded = module.dumps(value)
    if type(encoded) is not bytes:
        raise AssertionError("dumps must return bytes")
    decoded = json.loads(encoded, parse_constant=reject_constant)
    assert_same(decoded, value)
    # A serializer must not make its own mutated input the correctness reference.
    assert_same(value, json.loads(raw, parse_constant=reject_constant))
    return {
        "input_bytes": len(raw),
        "output_bytes": len(encoded),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "work_bytes": len(encoded),
    }


def timed_calls(function, argument, count):
    start = time.perf_counter_ns()
    for _ in range(count):
        function(argument)
    return time.perf_counter_ns() - start


def measure(function, argument, seconds, samples, warmups):
    """Include returned-value destruction; exclude preparation and cyclic GC."""
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        for _ in range(warmups):
            function(argument)
        target = seconds * 1e9
        count = 1
        elapsed = timed_calls(function, argument, count)
        while elapsed < min(target, 2_000_000) and count < 1_000_000:
            count *= 2
            elapsed = timed_calls(function, argument, count)
        count = max(1, min(1_000_000, math.ceil(count * target / max(elapsed, 1))))
        durations = [timed_calls(function, argument, count) for _ in range(samples)]
    finally:
        if enabled:
            gc.enable()
    latencies = [duration / count for duration in durations]
    return {
        "iterations_per_sample": count,
        "sample_elapsed_ns": durations,
        "sample_latency_ns": latencies,
        "median_latency_ns": statistics.median(latencies),
    }


def worker(payload):
    if payload["expected_sources"] != SOURCE_HASHES:
        raise ValueError("benchmark source changed; restart with a frozen runner")
    if payload["cpu"] is not None:
        if not hasattr(os, "sched_setaffinity"):
            raise ValueError("--cpu requires OS CPU-affinity support")
        os.sched_setaffinity(0, {payload["cpu"]})
    library = payload["library"]
    sys.path[:0] = library["pythonpath"]
    module = importlib.import_module(library["module"])
    metadata = module_metadata(library, module)
    if payload.get("expected_metadata") not in (None, metadata):
        raise ValueError(f"{library['name']} build or environment changed after verification")
    results = {}
    for document in payload["documents"]:
        raw, value = prepare_document(document, payload["directory"])
        for operation in payload["operations"]:
            name = operation + ":" + document["name"]
            if payload.get("active_cases") is not None and name not in payload["active_cases"]:
                continue
            try:
                checked = verify_operation(module, operation, raw, value)
                if payload["mode"] == "time":
                    expected = payload["expected_checks"][name]
                    if checked != expected:
                        raise AssertionError("correctness result changed after verification")
                    checked["timing"] = measure(
                        getattr(module, operation),
                        raw if operation == "loads" else value,
                        payload["seconds"], payload["samples"], payload["warmups"],
                    )
                results[name] = checked
            except (ValueError, TypeError, AssertionError) as error:
                raise ValueError(f"{library['name']} {name}: {error}") from error
        del raw, value
    return {"metadata": metadata, "cases": results}


def child(library, payload, hash_seed, timeout):
    environment = dict(os.environ, PYTHONHASHSEED=str(hash_seed), PYTHONNOUSERSITE="1")
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [library["python"], str(Path(__file__).resolve()), "_worker"],
        input=json.dumps(dict(payload, library=library, expected_sources=SOURCE_HASHES)),
        text=True, capture_output=True,
        check=False, env=environment, timeout=timeout,
    )
    if completed.returncode:
        raise ValueError(
            f"{library['name']} worker exited {completed.returncode}: {completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def verify_builds(libraries, payload, references, timeout):
    verified = {}
    for library in libraries:
        print(f"Checking {library['name']} before timing", file=sys.stderr, flush=True)
        verified[library["name"]] = child(library, dict(payload, mode="verify"), 1729, timeout)
    expected = verified[references[0]]["cases"]
    for name, result in verified.items():
        if result["cases"] != expected:
            differing = [case for case in expected if result["cases"].get(case) != expected[case]]
            raise ValueError(f"{name} output differs from {references[0]}: {differing}")
    return verified


def unique_cases(documents, operations, checks):
    """Avoid weighting copied documents and identical encoding inputs twice."""
    active, aliases, identities = [], {}, {}
    for document in documents:
        for operation in operations:
            name = operation + ":" + document["name"]
            digest = document["sha256"] if operation == "loads" else checks[name]["output_sha256"]
            identity = operation, digest
            if identity in identities:
                aliases[name] = identities[identity]
            else:
                identities[identity] = name
                active.append(name)
    return active, aliases


def library_order(libraries, repeat):
    # Rotate and reverse so the same build does not always run first.
    if len(libraries) == 2:
        return libraries if repeat % 2 == 0 else list(reversed(libraries))
    start = repeat % len(libraries)
    order = libraries[start:] + libraries[:start]
    return order if (repeat // len(libraries)) % 2 == 0 else list(reversed(order))


def summarize(runs, active, checks, references):
    names = list(runs[0]["libraries"])
    cases = {}
    for case in active:
        measurements = {}
        for name in names:
            values = [run["libraries"][name][case]["timing"]["median_latency_ns"] for run in runs]
            median = statistics.median(values)
            measurements[name] = {
                "latency_ns": median,
                "throughput_MB_s": checks[case]["work_bytes"] * 1000 / median,
                "process_medians_ns": values,
                "minimum_process_ns": min(values),
                "maximum_process_ns": max(values),
            }
        ratios = {}
        for reference in references:
            ratios[reference] = {}
            for name in names:
                if name == reference:
                    continue
                ratios[reference][name] = {
                    "latency_ratio": measurements[name]["latency_ns"] / measurements[reference]["latency_ns"],
                    "paired_ratios": [
                        left / right for left, right in zip(
                            measurements[name]["process_medians_ns"],
                            measurements[reference]["process_medians_ns"],
                        )
                    ],
                }
        cases[case] = dict(checks[case], measurements=measurements, ratios=ratios)
    geomeans = {}
    for reference in references:
        geomeans[reference] = {}
        for name in names:
            if name == reference:
                continue
            groups = {}
            for operation in ("loads", "dumps", "combined"):
                selected = [
                    row["ratios"][reference][name]["latency_ratio"]
                    for case, row in cases.items()
                    if operation == "combined" or case.startswith(operation + ":")
                ]
                if selected:
                    groups[operation] = {
                        "case_count": len(selected),
                        "latency_ratio": math.exp(statistics.fmean(math.log(value) for value in selected)),
                        "faster_cases": sum(value < 1 for value in selected),
                        "slower_cases": sum(value > 1 for value in selected),
                    }
            geomeans[reference][name] = groups
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
        "documents": documents, "operations": args.operations,
        "directory": str(Path(args.directory).resolve()), "cpu": args.cpu,
        "seconds": args.seconds, "samples": args.samples, "warmups": args.warmups,
    }
    verified = verify_builds(libraries, payload, references, args.timeout)
    checks = verified[references[0]]["cases"]
    active, aliases = unique_cases(documents, args.operations, checks)
    result = {
        "schema_version": 1,
        "benchmark": "public-corpus",
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
            "latency": "Nanoseconds per complete call, including returned-value destruction. Lower is better.",
            "throughput": "Decimal MB/s (1 MB = 1,000,000 bytes). Loads uses original input bytes; dumps uses output bytes. Higher is better.",
            "preparation": "Standard-library json.loads creates identical Python values. Downloads, file reads, hashing, preparation, and correctness checks are outside timing.",
            "correctness": "For requested operations, compare complete values and exact types, float bits, dictionary order, and encoded bytes across all builds before timing. Recheck each worker before measuring.",
            "geomean": "For each unique case, divide a library's median process latency by the reference's median process latency. Take the geometric mean of those ratios with equal case weights. Lower is better; 1 means equal latency.",
            "duplicates": "Loads deduplicates identical document SHA-256s. Dumps also deduplicates identical encoded outputs after exact-value checks. duplicate_cases lists omitted cases.",
            "gc": "Cyclic GC is collected and disabled around warmup/calibration/timing; reference-counted result destruction remains timed.",
            "cache": "Repeated calls use the same prepared input. These are warm repeated-call measurements, not cold-cache or startup measurements.",
            "samples_per_process": args.samples,
            "target_seconds_per_sample": args.seconds,
            "warmup_calls": args.warmups,
            "requested_cpu": args.cpu,
            "process_repeats": 0 if args.command == "verify" else args.repeats,
        },
        "runs": [],
    }
    if args.command == "verify":
        return result
    for repeat in range(args.repeats):
        order = library_order(libraries, repeat)
        shuffled = list(documents)
        random.Random(1729 + repeat).shuffle(shuffled)
        run = {
            "repeat": repeat + 1, "python_hash_seed": 1729 + repeat,
            "library_order": [library["name"] for library in order],
            "document_order": [document["name"] for document in shuffled],
            "libraries": {},
        }
        for library in order:
            name = library["name"]
            response = child(library, dict(
                payload, mode="time", documents=shuffled, active_cases=active,
                expected_metadata=verified[name]["metadata"], expected_checks=verified[name]["cases"],
            ), 1729 + repeat, args.timeout)
            run["libraries"][name] = response["cases"]
        result["runs"].append(run)
        print(f"Completed process repeat {repeat + 1} of {args.repeats}", file=sys.stderr, flush=True)
    result["summary"] = summarize(result["runs"], active, checks, references)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("list", "fetch", "verify", "run"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--manifest", type=Path, default=MANIFEST)
        subparser.add_argument("--cases", nargs="+")
        if command != "list":
            subparser.add_argument("--directory", type=Path, required=True)
        if command in ("verify", "run"):
            subparser.add_argument("--libraries", type=Path, required=True)
            subparser.add_argument("--reference", action="append", required=True, help="Library label; repeat for separate reference versions.")
            subparser.add_argument("--operations", nargs="+", choices=("loads", "dumps"), default=["loads", "dumps"])
            subparser.add_argument("--cpu", type=int)
            subparser.add_argument("--repeats", type=int, default=7, help="Independent processes per library.")
            subparser.add_argument("--samples", type=int, default=3, help="Timed samples per case in each process.")
            subparser.add_argument("--seconds", type=float, default=0.05, help="Target duration of each timed sample.")
            subparser.add_argument("--warmups", type=int, default=3)
            subparser.add_argument("--timeout", type=float, default=600, help="Maximum seconds for one child process.")
            subparser.add_argument("--output", type=Path, required=True)
    commands.add_parser("_worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.command == "_worker":
            print(json.dumps(worker(json.load(sys.stdin)), allow_nan=False))
        elif args.command in ("list", "fetch"):
            documents = select_documents(load_manifest(args.manifest), args.cases)
            for document in documents:
                if args.command == "fetch":
                    status = fetch_document(document, args.directory)
                    print(f"{document['name']}: {status}, SHA-256 verified")
                else:
                    print(f"{document['name']}\t{document['size_bytes']} bytes\t{document['suite']}\t{document['terms']}")
        else:
            if args.repeats < 1 or args.samples < 1 or args.warmups < 0:
                parser.error("repeats and samples must be positive; warmups must be nonnegative")
            if not math.isfinite(args.seconds) or not math.isfinite(args.timeout) or args.seconds <= 0 or args.timeout <= 0:
                parser.error("seconds and timeout must be finite and positive")
            if args.cpu is not None and args.cpu < 0:
                parser.error("cpu must be nonnegative")
            if len(set(args.operations)) != len(args.operations):
                parser.error("operations must not repeat")
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
            print(f"{len(result['active_cases'])} unique cases; result written to {args.output}")
    except (OSError, ValueError, AssertionError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
