"""Compare complete-load rejection latency and allocations, including exception release."""

import argparse
import datetime
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

# Python's safe-path mode omits the script directory from module lookup.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_public_corpus import library_order, load_libraries, measure, module_metadata
from bench_public_memory import measure_memray
from public_corpus import sha256_file


DEFAULT_SIZES = (64, 4096, 65536, 1048576)
DEFAULT_DEPTHS = (1025, 8192, 524288)

# Range and depth limits reject otherwise valid JSON; they are not syntax errors.
FAMILIES = {
    "syntax_early": "syntax",
    "syntax_late": "syntax",
    "unfinished_string": "syntax",
    "unfinished_escape": "syntax",
    "unfinished_unicode_escape": "syntax",
    "utf8_early": "utf8",
    "utf8_late": "utf8",
    "number_overflow": "numeric_range",
    "trailing_input": "syntax",
    "depth_limit": "depth_limit",
}
METRICS = {
    "latency": ("median_latency_ns",),
    "memray": ("allocation_requests", "total_allocated_bytes", "peak_live_bytes"),
}
SOURCE_FILES = {
    "rejection_runner_sha256": Path(__file__),
    "runner_sha256": Path(__file__).with_name("bench_public_corpus.py"),
    "memory_runner_sha256": Path(__file__).with_name("bench_public_memory.py"),
    "allocation_helper_sha256": Path(__file__).with_name("allocation_stats.py"),
    "corpus_helper_sha256": Path(__file__).with_name("public_corpus.py"),
}


def source_hashes():
    return {name: sha256_file(path) for name, path in SOURCE_FILES.items()}


SOURCE_HASHES = source_hashes()


def build_input(family, parameter):
    """Generate bounded bytes; parameter is a depth or the exact input size."""
    if family not in FAMILIES:
        raise ValueError(f"unknown rejection family: {family}")
    minimum, maximum = (1025, 524288) if family == "depth_limit" else (64, 1048576)
    if type(parameter) is not int or not minimum <= parameter <= maximum:
        raise ValueError(f"{family} requires an integer from {minimum} to {maximum}")
    if family == "depth_limit":
        return b"[" * parameter + b"0" + b"]" * parameter
    if family.startswith("syntax_") or family == "trailing_input":
        size = parameter - 2 if family == "trailing_input" else parameter
        count = (size - 1) // 8
        array = b"[" + b'{"k":0},' * (count - 1) + b'{"k":0}]'
        if family == "syntax_early":
            array = b"!" + array[1:]
        elif family == "syntax_late":
            array = array[:-1] + b"}"
        padded = array + b" " * (size - len(array))
        return padded + b" 0" if family == "trailing_input" else padded
    if family == "unfinished_string":
        return b'"' + b"a" * (parameter - 1)
    if family == "unfinished_escape":
        return b'"' + b"a" * (parameter - 2) + b"\\"
    if family == "unfinished_unicode_escape":
        return b'"' + b"a" * (parameter - 5) + b"\\u12"
    if family.startswith("utf8_"):
        count, padding = divmod(parameter - 3, 3)
        valid = b"\xe2\x98\x83" * count + b"x" * padding
        return b'"\xff' + valid + b'"' if family == "utf8_early" else b'"' + valid + b'\xff"'
    return b"9" * (parameter - 4) + b"e400"


def describe_input(family, parameter, raw):
    return {
        "name": f"{family}_{parameter}",
        "family": family,
        "rejection_category": FAMILIES[family],
        "input_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "depth": parameter if family == "depth_limit" else None,
    }


def select_cases(families, sizes, depths):
    families = list(FAMILIES) if families is None else families
    for values, label in ((families, "families"), (sizes, "sizes"), (depths, "depths")):
        if not values or len(set(values)) != len(values):
            raise ValueError(f"{label} must be nonempty and must not repeat")
    unknown = set(families) - FAMILIES.keys()
    if unknown:
        raise ValueError(f"unknown rejection families: {sorted(unknown)}")
    cases = []
    for family in families:
        for parameter in depths if family == "depth_limit" else sizes:
            raw = build_input(family, parameter)
            cases.append(describe_input(family, parameter, raw))
            del raw
    return cases


def prepare_input(case):
    parameter = case["depth"] if case["family"] == "depth_limit" else case["input_bytes"]
    raw = build_input(case["family"], parameter)
    if describe_input(case["family"], parameter, raw) != case:
        raise ValueError(f"{case['name']} input descriptor or SHA-256 changed")
    return raw


def rejection_call(function, error_type):
    """Release the expected exception before returning; propagate every other error."""
    if not isinstance(error_type, type) or not issubclass(error_type, Exception):
        raise ValueError("JSONDecodeError must be an exception class")

    def reject(raw):
        try:
            function(raw)
        except error_type:
            return None
        raise AssertionError("loads accepted an input that must be rejected")

    return reject


def verify_rejection(module, raw):
    try:
        module.loads(raw)
    except module.JSONDecodeError as error:
        return {"exception_type": f"{type(error).__module__}.{type(error).__qualname__}"}
    raise AssertionError("loads accepted an input that must be rejected")


def memray_metadata(version):
    """Fingerprint the profiler outside capture; latency workers never call this."""
    return module_metadata({
        "name": "memray", "module": "memray", "expected_version": version, "pythonpath": [],
    }, importlib.import_module("memray"))


def worker(payload):
    if payload["expected_sources"] != SOURCE_HASHES or source_hashes() != SOURCE_HASHES:
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
    profiler = None
    if payload.get("memray_version") is not None and (
        payload["mode"] == "verify" or payload.get("metric") == "memray"
    ):
        profiler = memray_metadata(payload["memray_version"])
        if payload.get("expected_memray_metadata") not in (None, profiler):
            raise ValueError("Memray build or environment changed after verification")
    function = rejection_call(module.loads, module.JSONDecodeError)
    if payload["mode"] == "verify":
        checks = {}
        for case in payload["cases"]:
            raw = prepare_input(case)
            checks[case["name"]] = {
                **verify_rejection(module, raw), "input_sha256": case["sha256"],
            }
            del raw
        result = {"checks": checks}
    elif payload["mode"] == "measure":
        raw = prepare_input(payload["case"])
        if payload["metric"] == "latency":
            if "memray" in sys.modules:
                raise ValueError("latency workers must not import Memray")
            measurement = measure(
                function, raw, payload["seconds"], payload["samples"], payload["latency_warmups"],
            )
            if "memray" in sys.modules:
                raise ValueError("latency workers must not import Memray")
        elif payload["metric"] == "memray":
            measurement = measure_memray(
                function, raw, payload["memray_calls"], payload["memray_warmups"],
                Path(payload["profile"]), payload["memray_version"],
            )
        else:
            raise ValueError(f"unknown metric: {payload['metric']}")
        result = {"measurement": measurement}
    else:
        raise ValueError(f"unknown worker mode: {payload['mode']}")
    if source_hashes() != SOURCE_HASHES or module_metadata(library, module) != metadata:
        raise ValueError(f"{library['name']} sources, build, or environment changed during the worker")
    if profiler is not None and memray_metadata(payload["memray_version"]) != profiler:
        raise ValueError("Memray build or environment changed during the worker")
    return {"metadata": metadata, "memray_metadata": profiler, **result}


def child(library, payload, hash_seed, timeout):
    environment = dict(
        os.environ, PYTHONHASHSEED=str(hash_seed), PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
    )
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    completed = subprocess.run(
        [library["python"], str(Path(__file__).resolve()), "_worker"],
        input=json.dumps(dict(payload, library=library, expected_sources=SOURCE_HASHES)),
        text=True, capture_output=True, check=False, env=environment, timeout=timeout,
    )
    if completed.returncode:
        raise ValueError(
            f"{library['name']} {payload['mode']} worker exited {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def summarize(runs, cases, metrics):
    """Keep separate per-case medians; early rejection has no parsed-byte throughput."""
    summary = {}
    for case in cases:
        name = case["name"]
        summary[name] = {}
        for metric in metrics:
            summary[name][metric] = {
                library: {
                    field: statistics.median(
                        run["libraries"][library][name][metric][field] for run in runs
                    )
                    for field in METRICS[metric]
                }
                for library in runs[0]["libraries"]
            }
    return {"cases": summary}


def compare(args):
    cases = select_cases(args.cases, args.sizes, args.depths)
    libraries = load_libraries(args.libraries)
    verified = {}
    for library in libraries:
        print(f"Checking {library['name']} rejects all {len(cases)} inputs", file=sys.stderr, flush=True)
        verified[library["name"]] = child(library, {
            "mode": "verify", "cases": cases, "cpu": args.cpu,
            "memray_version": args.memray_version if "memray" in args.metrics else None,
        }, 1729, args.timeout)
    profile_directory = None
    if "memray" in args.metrics:
        args.profiles.mkdir(parents=True, exist_ok=True)
        profile_directory = Path(tempfile.mkdtemp(prefix="rejections-", dir=args.profiles))
        print(f"Raw Memray captures: {profile_directory}", file=sys.stderr, flush=True)
    result = {
        "schema_version": 1,
        "benchmark": "complete-load-rejections",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        **SOURCE_HASHES,
        "cases": cases,
        "libraries": {name: row["metadata"] for name, row in verified.items()},
        "memray": {name: row["memray_metadata"] for name, row in verified.items()},
        "verification": {name: row["checks"] for name, row in verified.items()},
        "method": {
            "operation": "loads",
            "input_type": "bytes",
            "metrics": args.metrics,
            "direction": "Lower is better for latency, allocation requests, allocated bytes, and tracked peak bytes.",
            "included": "Each call includes catching and releasing JSONDecodeError, its traceback, and any error-owned source string. No exception is retained between calls. Acceptance or another exception type fails the comparison.",
            "preparation": "Generic inputs are generated and SHA-256 checked before measurement. Each measurement worker retains only its selected input. Imports, correctness preflight, input preparation, and fingerprinting are excluded.",
            "processes": "All libraries reject every selected case in separate correctness processes before measurement. Each library, case, metric, and repeat then runs in a fresh interpreter. Case order is shuffled deterministically; library order rotates by repeat.",
            "gc": "Cyclic GC is collected and disabled before warmups and restored afterward. Expected exceptions are released by reference counting in CPython; this does not measure delayed collection of exception cycles.",
            "latency": "Use bench_public_corpus.measure without Memray. Warmups and calibration are excluded. Three samples per process by default; retain every elapsed time and call count.",
            "memray": "Use bench_public_memory.measure_memray with Python allocator tracing and no native stacks. Count allocation-kind records, including zero-byte requests; exclude deallocation records. Realloc counts its full requested new size. Includes the tracked loop and exception release; excludes imports, input generation, warmups, and capture analysis.",
            "memory_limits": "Tracked peak live bytes are not process RSS. Preexisting allocations are excluded. Peaks are not divided by calls. Repeated warmed calls do not describe first-use allocation cost.",
            "summary": "Per-case medians across processes. Latency summarizes each process's sample median. Raw measurements remain in runs. No throughput, geomean, or valid-document score is computed for rejected inputs.",
            "latency_samples": args.samples,
            "latency_target_seconds_per_sample": args.seconds,
            "latency_warmup_calls": args.latency_warmups,
            "memray_tracked_calls": args.memray_calls,
            "memray_warmup_calls": args.memray_warmups,
            "memray_version": args.memray_version if "memray" in args.metrics else None,
            "process_repeats": args.repeats,
            "preflight_python_hash_seed": 1729,
            "requested_cpu": args.cpu,
            "worker_timeout_seconds": args.timeout,
        },
        "runs": [],
    }
    for repeat in range(args.repeats):
        order = library_order(libraries, repeat)
        shuffled = list(cases)
        random.Random(1729 + repeat).shuffle(shuffled)
        run = {
            "repeat": repeat + 1, "python_hash_seed": 1729 + repeat,
            "library_order": [library["name"] for library in order],
            "case_order": [case["name"] for case in shuffled],
            "metric_order": args.metrics,
            "libraries": {library["name"]: {} for library in order},
        }
        for case in shuffled:
            for library in order:
                name = library["name"]
                run["libraries"][name][case["name"]] = {}
                for metric in args.metrics:
                    profile = None if metric == "latency" else str(
                        profile_directory / f"{repeat + 1:03d}.{name}.{case['name']}.bin"
                    )
                    response = child(library, {
                        "mode": "measure", "metric": metric, "case": case, "cpu": args.cpu,
                        "seconds": args.seconds, "samples": args.samples,
                        "latency_warmups": args.latency_warmups,
                        "memray_calls": args.memray_calls, "memray_warmups": args.memray_warmups,
                        "profile": profile, "memray_version": args.memray_version,
                        "expected_metadata": verified[name]["metadata"],
                        "expected_memray_metadata": verified[name]["memray_metadata"],
                    }, 1729 + repeat, args.timeout)
                    if response["metadata"] != verified[name]["metadata"]:
                        raise ValueError(f"{name} build or environment changed after verification")
                    measurement = response["measurement"]
                    expected_profiler = verified[name]["memray_metadata"] if metric == "memray" else None
                    if response["memray_metadata"] != expected_profiler or (
                        metric == "memray" and measurement["memray_version"] != args.memray_version
                    ):
                        raise ValueError("Memray build or version changed after verification")
                    run["libraries"][name][case["name"]][metric] = measurement
        result["runs"].append(run)
        print(f"Completed rejection repeat {repeat + 1} of {args.repeats}", file=sys.stderr, flush=True)
    if source_hashes() != SOURCE_HASHES:
        raise ValueError("benchmark source changed during the comparison")
    result["summary"] = summarize(result["runs"], cases, args.metrics)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--libraries", type=Path, required=True)
    run.add_argument("--cases", nargs="+", choices=tuple(FAMILIES), help="Select rejection families.")
    run.add_argument("--sizes", nargs="+", type=int, default=list(DEFAULT_SIZES), help="Bytes per non-depth input, from 64 to 1048576.")
    run.add_argument("--depths", nargs="+", type=int, default=list(DEFAULT_DEPTHS), help="Array depths, from 1025 to 524288.")
    run.add_argument("--metrics", nargs="+", choices=tuple(METRICS), default=list(METRICS))
    run.add_argument("--cpu", type=int)
    run.add_argument("--repeats", type=int, default=3, help="Fresh processes per library, case, and metric.")
    run.add_argument("--samples", type=int, default=3, help="Timed samples per latency worker.")
    run.add_argument("--seconds", type=float, default=0.03, help="Target seconds per timed sample.")
    run.add_argument("--latency-warmups", type=int, default=3)
    run.add_argument("--memray-calls", type=int, default=1)
    run.add_argument("--memray-warmups", type=int, default=10)
    run.add_argument("--memray-version", default="1.20.0", help="Require this Memray version.")
    run.add_argument("--profiles", type=Path, help="Store raw Memray captures in a new subdirectory here.")
    run.add_argument("--timeout", type=float, default=120, help="Maximum seconds for one worker.")
    run.add_argument("--output", type=Path, required=True)
    commands.add_parser("_worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.command == "_worker":
            print(json.dumps(worker(json.load(sys.stdin)), allow_nan=False))
            return
        if min(args.repeats, args.samples, args.memray_calls) < 1:
            parser.error("repeats, samples, and tracked calls must be positive")
        if min(args.latency_warmups, args.memray_warmups) < 0:
            parser.error("warmups must be nonnegative")
        if any(not math.isfinite(value) or value <= 0 for value in (args.seconds, args.timeout)):
            parser.error("seconds and timeout must be finite and positive")
        if args.cpu is not None and args.cpu < 0:
            parser.error("cpu must be nonnegative")
        if len(set(args.metrics)) != len(args.metrics):
            parser.error("metrics must not repeat")
        if "memray" in args.metrics and (args.profiles is None or not args.memray_version):
            parser.error("Memray measurements require --profiles and a nonempty --memray-version")
        if args.output.exists() or not args.output.parent.is_dir():
            parser.error("output must be a new file in an existing directory")
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
            if args.output.exists():
                raise ValueError("output was created during the comparison; refusing to replace it")
            os.replace(temporary, args.output)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(f"{len(result['cases'])} rejection cases; result written to {args.output}")
    except (ImportError, OSError, ValueError, AssertionError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
