"""Compare whole-process peak RSS in fresh Linux processes, without Memray."""

import argparse
import dataclasses
import gc
import importlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile


@dataclasses.dataclass
class Record:
    id: int
    name: str


CASES = (
    "loads_medium",
    "loads_large",
    "dumps_medium",
    "fragments_1000",
    "dataclasses_1000",
    "numpy_float32",
    "late_default",
)


def rss():
    fields = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        name, _, value = line.partition(":")
        if name in ("VmRSS", "VmHWM"):
            fields[name + "_kib"] = int(value.split()[0])
    fields["ru_maxrss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return fields


def worker(module_name, case, calls, fixtures):
    startup = rss()
    module = importlib.import_module(module_name)
    kwargs = {}
    function = module.dumps
    numpy_version = None
    if case.startswith("loads_"):
        value = (fixtures / case).read_bytes()
        function = module.loads
    elif case == "dumps_medium":
        value = [{"id": i, "score": i / 7, "name": f"item-{i}"} for i in range(1000)]
    elif case == "fragments_1000":
        value = [module.Fragment(b'{"x":[1,2,3]}')] * 1000
    elif case == "dataclasses_1000":
        value = [Record(i, f"item-{i}") for i in range(1000)]
    elif case == "numpy_float32":
        import numpy

        numpy_version = numpy.__version__
        value = numpy.arange(100000, dtype=numpy.float32).reshape(25000, 4)
        kwargs["option"] = module.OPT_SERIALIZE_NUMPY
    else:
        value = ["x" * 4096] * 5000 + [object()]
        kwargs["default"] = lambda _: None
    gc.collect()
    before = rss()
    function(value, **kwargs)
    first = rss()
    for _ in range(calls - 1):
        function(value, **kwargs)
    final = rss()
    print(json.dumps({"module": module_name, "version": module.__version__,
                      "numpy": numpy_version, "case": case, "startup": startup,
                      "before": before, "first": first, "final": final}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("jsonmodem", "orjson"))
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--calls", type=int, default=10)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("RSS measurement requires Linux /proc/self/status")
    if args.calls < 1 or args.runs < 1:
        parser.error("--calls and --runs must be positive")
    if (args.worker or args.generate) and args.fixtures is None:
        parser.error("child process requires --fixtures")
    if args.worker and args.case is None:
        parser.error("--worker requires --case")
    if not (args.worker or args.generate) and args.output is None:
        parser.error("--output is required")
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    if args.generate:
        for name, count in (("loads_medium", 1000), ("loads_large", 100000)):
            values = [{"id": i, "score": i / 7, "name": f"item-{i}"} for i in range(count)]
            (args.fixtures / name).write_bytes(json.dumps(values, separators=(",", ":")).encode())
        return
    if args.worker:
        worker(args.worker, args.case, args.calls, args.fixtures)
        return
    samples = []
    with tempfile.TemporaryDirectory(prefix="jsonmodem-rss-") as fixtures:
        # Building decoded fixtures in a worker would raise its RSS before loads().
        subprocess.run([sys.executable, __file__, "--generate", "--fixtures", fixtures], check=True)
        for case in CASES:
            for run in range(args.runs):
                modules = ("jsonmodem", "orjson") if run % 2 == 0 else ("orjson", "jsonmodem")
                for module in modules:
                    completed = subprocess.run(
                        [sys.executable, __file__, "--worker", module, "--case", case,
                         "--calls", str(args.calls), "--fixtures", fixtures],
                        check=True, capture_output=True, text=True, timeout=60,
                    )
                    sample = json.loads(completed.stdout)
                    sample["run"] = run
                    samples.append(sample)
            for module in ("jsonmodem", "orjson"):
                rows = [s for s in samples if s["case"] == case and s["module"] == module]
                baseline = statistics.median(s["before"]["VmRSS_kib"] for s in rows) / 1024
                peak = statistics.median(s["final"]["VmHWM_kib"] for s in rows) / 1024
                print(f"{case:20} {module:10} pre-call RSS {baseline:6.2f} MiB; "
                      f"peak RSS {peak:6.2f} MiB", flush=True)
    args.output.write_text(json.dumps({"python": platform.python_version(),
                                      "platform": platform.platform(), "runs": args.runs,
                                      "calls": args.calls, "samples": samples}, indent=2) + "\n")


if __name__ == "__main__":
    main()
