"""Compare tracked allocations and separate fresh-process RSS on public JSON files."""

import argparse
import datetime
import gc
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

from allocation_stats import summarize_allocations
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
    "memory_runner_sha256": sha256_file(__file__),
    "allocation_helper_sha256": sha256_file(Path(__file__).with_name("allocation_stats.py")),
}

# These are separate measurements, not interchangeable estimates of memory use.
METRICS = {
    "memray": ("allocation_requests", "total_allocated_bytes", "peak_live_bytes"),
    "rss": ("peak_rss_bytes", "prepared_rss_bytes", "first_result_rss_bytes"),
}


def prepare_input(document, directory, operation):
    """Loads retains only bytes; dumps retains one stdlib tree and releases bytes."""
    raw = read_document(document, directory)
    if operation == "loads":
        return raw
    if operation == "dumps":
        return json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
    raise ValueError(f"unknown operation: {operation}")


def discard_calls(function, argument, count):
    for _ in range(count):
        result = function(argument)
        # Assignment alone would retain the previous result while making the next.
        del result


def rss_snapshot():
    """Read VmRSS, VmHWM, and ru_maxrss, all normalized to bytes."""
    if sys.platform != "linux":
        raise ValueError("RSS measurements require Linux /proc/self/status")
    import resource

    fields = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        name, _, value = line.partition(":")
        if name in ("VmRSS", "VmHWM"):
            amount, unit = value.split()
            if unit != "kB" or not amount.isdecimal():
                raise ValueError(f"unexpected /proc/self/status {name} units or value")
            fields[name] = int(amount) * 1024
    if set(fields) != {"VmRSS", "VmHWM"}:
        raise ValueError("/proc/self/status did not report VmRSS and VmHWM")
    return {
        "rss_bytes": fields["VmRSS"],
        "peak_rss_bytes": fields["VmHWM"],
        "ru_maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }


def measure_rss(function, argument, calls, startup):
    """Keep the first result alive for one snapshot; release each result in turn."""
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        snapshots = {"startup": startup, "prepared": rss_snapshot()}
        result = function(argument)
        snapshots["first_result_alive"] = rss_snapshot()
        del result
        snapshots["first_result_released"] = rss_snapshot()
        discard_calls(function, argument, calls - 1)
        snapshots["after_calls"] = rss_snapshot()
    finally:
        if enabled:
            gc.enable()
    return {
        "calls": calls,
        "warmup_calls": 0,
        "peak_rss_bytes": snapshots["after_calls"]["peak_rss_bytes"],
        "prepared_rss_bytes": snapshots["prepared"]["rss_bytes"],
        "first_result_rss_bytes": snapshots["first_result_alive"]["rss_bytes"],
        "snapshots": snapshots,
    }


def measure_memray(function, argument, calls, warmups, profile, expected_version):
    import memray

    if expected_version is not None and memray.__version__ != expected_version:
        raise ValueError(f"Memray version is {memray.__version__}, expected {expected_version}")
    tracker = memray.Tracker(
        str(profile), trace_python_allocators=True, native_traces=False,
        file_format=memray.FileFormat.ALL_ALLOCATIONS,
    )
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        discard_calls(function, argument, warmups)
        with tracker:
            discard_calls(function, argument, calls)
    finally:
        if enabled:
            gc.enable()
    summary = summarize_allocations(profile)
    if not summary["trace_python_allocators"] or summary["native_traces"]:
        raise ValueError("Memray capture flags differ from the requested measurement")
    return {
        **summary,
        "memray_version": memray.__version__,
        "calls": calls,
        "warmup_calls": warmups,
        "capture": {
            "name": profile.name,
            "size_bytes": profile.stat().st_size,
            "sha256": sha256_file(profile),
        },
    }


def worker(payload):
    if payload["expected_sources"] != SOURCE_HASHES:
        raise ValueError("benchmark source changed; restart with a frozen runner")
    if payload["cpu"] is not None:
        if not hasattr(os, "sched_setaffinity"):
            raise ValueError("--cpu requires OS CPU-affinity support")
        os.sched_setaffinity(0, {payload["cpu"]})
    metric = payload["metric"]
    if metric not in METRICS:
        raise ValueError(f"unknown metric: {metric}")
    startup = rss_snapshot() if metric == "rss" else None
    library = payload["library"]
    sys.path[:0] = library["pythonpath"]
    module = importlib.import_module(library["module"])
    argument = prepare_input(payload["document"], payload["directory"], payload["operation"])
    function = getattr(module, payload["operation"])
    if metric == "rss":
        if "memray" in sys.modules:
            raise ValueError("RSS workers must not import Memray")
        measurement = measure_rss(function, argument, payload["rss_calls"], startup)
        if "memray" in sys.modules:
            raise ValueError("RSS workers must not import Memray")
    else:
        measurement = measure_memray(
            function, argument, payload["calls"], payload["warmups"],
            Path(payload["profile"]), payload["memray_version"],
        )
    # File hashing and metadata construction must not raise the reported RSS peak.
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
            f"{library['name']} {payload['metric']} worker exited {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return json.loads(completed.stdout)


def summarize(runs, active, checks, references, metrics):
    cases = {}
    names = list(runs[0]["libraries"])
    for case in active:
        cases[case] = dict(checks[case])
        for metric in metrics:
            measurements = {}
            for name in names:
                samples = [
                    {field: run["libraries"][name][case][metric][field] for field in METRICS[metric]}
                    for run in runs
                ]
                measurements[name] = {
                    **{field: statistics.median(sample[field] for sample in samples) for field in METRICS[metric]},
                    "process_samples": samples,
                }
            ratios = {}
            for reference in references:
                ratios[reference] = {
                    name: {
                        field: measurements[name][field] / measurements[reference][field]
                        if measurements[reference][field] else None
                        for field in METRICS[metric]
                    }
                    for name in names if name != reference
                }
            cases[case][metric] = {"measurements": measurements, "ratios": ratios}
    return {"cases": cases}


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
    }
    verified = verify_builds(libraries, payload, references, args.timeout)
    checks = verified[references[0]]["cases"]
    active, aliases = unique_cases(documents, args.operations, checks)
    profile_directory = None
    if "memray" in args.metrics:
        args.profiles.mkdir(parents=True, exist_ok=True)
        profile_directory = Path(tempfile.mkdtemp(prefix="public-memory-", dir=args.profiles))
        print(f"Raw Memray captures: {profile_directory}", file=sys.stderr, flush=True)
    result = {
        "schema_version": 1,
        "benchmark": "public-corpus-memory",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "manifest": {"name": manifest["name"], "sha256": sha256_file(args.manifest)},
        **SOURCE_HASHES,
        "documents": documents,
        "references": references,
        "libraries": {name: row["metadata"] for name, row in verified.items()},
        "verification": {name: row["cases"] for name, row in verified.items()},
        "active_cases": active,
        "duplicate_cases": aliases,
        "memray_version": args.memray_version if "memray" in args.metrics else None,
        "method": {
            "metrics": args.metrics,
            "direction": "Lower is better for allocation requests, allocated bytes, tracked peak bytes, and RSS. These are different quantities; do not compare them to one another.",
            "processes": "Each library, case, metric, and repeat runs in a fresh process. Correctness checks run in separate processes, using the timing runner's exact-value and encoded-byte checks.",
            "preparation": "Loads retains only hash-verified original bytes. Dumps retains one standard-library decoded input and releases the original bytes. No reference output is retained in memory workers.",
            "gc": "Cyclic GC is collected and disabled before warmup or RSS calls, then restored. Every returned value is destroyed before the next call.",
            "memray": "Full allocation captures with Python allocator tracing and no native stacks. Count allocation-kind records, including zero-byte requests; exclude FREE, PYMALLOC_FREE, and MUNMAP. Realloc counts its full requested new size. Peak is Memray's tracked live-byte high-water mark, not RSS.",
            "memray_excludes": "Imports, input preparation, warmup allocations, preexisting live allocations, and capture analysis. The recorded loop and returned-value destruction are included. Peaks are not divided by calls.",
            "rss": "Linux /proc/self/status VmHWM after all calls is the whole-process peak RSS. VmRSS is current RSS; ru_maxrss is recorded separately. All source KiB values are converted to bytes.",
            "rss_limits": "RSS includes interpreter/imports, preparation, results, native temporaries, and retained allocator pages. Preparation can set the peak before the first call. Neither high-water mark is reset; subtracting a baseline does not isolate operation-only memory. Snapshot overhead is included.",
            "cache": "Memray uses the selected warmup count. RSS has no preliminary library calls. Neither mode promises cold OS caches or excludes interpreter startup effects on RSS.",
            "summary": "Per-case medians of fresh-process results, with every process sample retained. Ratios divide those medians by the labeled reference, or null if the reference is zero. There is no overall memory geomean or instrumented latency.",
            "duplicates": "Loads deduplicates original document hashes. Dumps deduplicates exact encoded outputs after full correctness checks. duplicate_cases lists omitted cases.",
            "memray_tracked_calls": args.calls,
            "memray_warmup_calls": args.warmups,
            "rss_calls": args.rss_calls,
            "rss_warmup_calls": 0,
            "process_repeats": args.repeats,
            "requested_cpu": args.cpu,
        },
        "runs": [],
    }
    for repeat in range(args.repeats):
        order = library_order(libraries, repeat)
        shuffled = list(documents)
        random.Random(1729 + repeat).shuffle(shuffled)
        run = {
            "repeat": repeat + 1, "python_hash_seed": 1729 + repeat,
            "library_order": [library["name"] for library in order],
            "document_order": [document["name"] for document in shuffled],
            "metric_order": args.metrics,
            "libraries": {library["name"]: {} for library in order},
        }
        for document in shuffled:
            for operation in args.operations:
                case = operation + ":" + document["name"]
                if case not in active:
                    continue
                for library in order:
                    name = library["name"]
                    run["libraries"][name][case] = {}
                    for metric in args.metrics:
                        profile = None if metric == "rss" else str(
                            profile_directory / f"{repeat + 1:03d}.{name}.{operation}.{document['name']}.bin"
                        )
                        response = child(library, {
                            "document": document, "operation": operation, "metric": metric,
                            "directory": payload["directory"], "cpu": args.cpu,
                            "calls": args.calls, "warmups": args.warmups, "rss_calls": args.rss_calls,
                            "profile": profile, "memray_version": result["memray_version"],
                            "expected_metadata": verified[name]["metadata"],
                        }, 1729 + repeat, args.timeout)
                        if response["metadata"] != verified[name]["metadata"]:
                            raise ValueError(f"{name} build or environment changed after verification")
                        measurement = response["measurement"]
                        if metric == "memray":
                            if result["memray_version"] not in (None, measurement["memray_version"]):
                                raise ValueError("Memray versions differ across memory workers")
                            result["memray_version"] = measurement["memray_version"]
                        run["libraries"][name][case][metric] = measurement
        result["runs"].append(run)
        print(f"Completed memory repeat {repeat + 1} of {args.repeats}", file=sys.stderr, flush=True)
    result["summary"] = summarize(result["runs"], active, checks, references, args.metrics)
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
    run.add_argument("--operations", nargs="+", choices=("loads", "dumps"), default=["loads", "dumps"])
    run.add_argument("--metrics", nargs="+", choices=tuple(METRICS), default=list(METRICS))
    run.add_argument("--cpu", type=int)
    run.add_argument("--repeats", type=int, default=3, help="Fresh processes per library, case, and metric.")
    run.add_argument("--calls", type=int, default=1, help="Memray-tracked calls per process.")
    run.add_argument("--warmups", type=int, default=10, help="Calls before Memray starts; zero means no warmup.")
    run.add_argument("--rss-calls", type=int, default=10, help="RSS calls per fresh process, without warmup.")
    run.add_argument("--memray-version", help="Require this profiler version; otherwise require all workers to match the first.")
    run.add_argument("--profiles", type=Path, help="Store raw Memray captures in a new subdirectory here.")
    run.add_argument("--timeout", type=float, default=600, help="Maximum seconds for one worker.")
    run.add_argument("--output", type=Path, required=True)
    commands.add_parser("_worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.command == "_worker":
            print(json.dumps(worker(json.load(sys.stdin)), allow_nan=False))
            return
        if min(args.repeats, args.calls, args.rss_calls) < 1 or args.warmups < 0:
            parser.error("repeats and call counts must be positive; warmups must be nonnegative")
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            parser.error("timeout must be finite and positive")
        if args.cpu is not None and args.cpu < 0:
            parser.error("cpu must be nonnegative")
        if len(set(args.operations)) != len(args.operations) or len(set(args.metrics)) != len(args.metrics):
            parser.error("operations and metrics must not repeat")
        if "memray" in args.metrics and args.profiles is None:
            parser.error("Memray measurements require --profiles")
        if "rss" in args.metrics and sys.platform != "linux":
            parser.error("RSS measurements require Linux /proc/self/status")
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
    except (ImportError, OSError, ValueError, AssertionError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
