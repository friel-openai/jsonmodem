"""Pinned, alternating complete-document benchmarks, not incremental parsing."""

from __future__ import annotations

import argparse
import array
import gc
import json
import os
import platform
import statistics
import time

import jsonmodem
import orjson


PAYLOADS = {
    "small": {"id": 42, "ok": True, "name": "jsonmodem", "tags": ["a", "b", "c"]},
    "medium": [
        {"id": index, "score": index / 7, "active": index % 3 == 0, "name": f"item-{index}"}
        for index in range(1_000)
    ],
    "integers": list(range(-5_000, 5_000)),
    "floats": [index / 7 for index in range(10_000)],
    "strings": [f"string-{index}-abcdefghijklmnopqrstuvwxyz" for index in range(1_000)],
    "escaped": [{"text": 'quote: " slash: \\ newline: \n unicode: \u2603'}] * 1_000,
    "long_string": "abcdefghijklmnopqrstuvxyz0123456789" * 4_096,
}

LOAD_INPUTS = {
    "bytes": bytes,
    "bytearray": bytearray,
    "memoryview": memoryview,
    "array_view": lambda data: memoryview(array.array("B", data)),
}


def elapsed(function, argument, iterations):
    enabled = gc.isenabled()
    gc.disable()
    try:
        start = time.perf_counter_ns()
        for _ in range(iterations):
            function(argument)
        return (time.perf_counter_ns() - start) / iterations
    finally:
        if enabled:
            gc.enable()


def measure(ours, theirs, argument, rounds, seconds):
    iterations = 1
    while True:
        duration = max(elapsed(ours, argument, iterations), elapsed(theirs, argument, iterations))
        if duration * iterations >= seconds * 1e9:
            break
        iterations *= 2
    samples = {"jsonmodem": [], "orjson": []}
    for round_index in range(rounds):
        order = [("jsonmodem", ours), ("orjson", theirs)]
        if round_index % 2:
            order.reverse()
        for name, function in order:
            samples[name].append(elapsed(function, argument, iterations))
    ours_ns = statistics.median(samples["jsonmodem"])
    theirs_ns = statistics.median(samples["orjson"])
    return {
        "iterations": iterations,
        "jsonmodem_ns": ours_ns,
        "orjson_ns": theirs_ns,
        "ratio": statistics.median(a / b for a, b in zip(samples["jsonmodem"], samples["orjson"])),
        "samples_ns": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Write timings and samples as JSON")
    parser.add_argument("--rounds", type=int, default=11)
    parser.add_argument("--seconds", type=float, default=0.03)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--workloads", nargs="+", choices=PAYLOADS, default=list(PAYLOADS))
    parser.add_argument("--operations", nargs="+", choices=["loads", "dumps"], default=["loads", "dumps"])
    parser.add_argument("--loads-inputs", nargs="+", choices=LOAD_INPUTS, default=["bytes"])
    args = parser.parse_args()
    cpu = args.cpu
    if hasattr(os, "sched_getaffinity"):
        cpu = min(os.sched_getaffinity(0)) if cpu is None else cpu
        os.sched_setaffinity(0, {cpu})
    result = {
        "python": platform.python_version(), "machine": platform.machine(),
        "orjson": orjson.__version__, "jsonmodem": jsonmodem.__version__,
        "cpu": cpu, "rounds": args.rounds, "workloads": [],
    }
    print(f"Python {result['python']}; orjson {result['orjson']}; CPU {cpu}; {args.rounds} measurements per library")
    print(f"{'operation':<10} {'payload':<14} {'input':<12} {'jsonmodem ns':>14} {'orjson ns':>12} {'ratio':>8}")
    for name in args.workloads:
        value = PAYLOADS[name]
        document = orjson.dumps(value)
        for operation in args.operations:
            inputs = [(kind, LOAD_INPUTS[kind](document)) for kind in args.loads_inputs] if operation == "loads" else [("object", value)]
            for kind, argument in inputs:
                ours, theirs = getattr(jsonmodem, operation), getattr(orjson, operation)
                a, b = ours(argument), theirs(argument)
                if operation == "loads":
                    assert a == b
                else:
                    assert json.loads(a) == json.loads(b)
                measurement = measure(ours, theirs, argument, args.rounds, args.seconds)
                measurement.update(operation=operation, payload=name, input_type=kind, bytes=len(document), exact_match=a == b)
                result["workloads"].append(measurement)
                print(f"{operation:<10} {name:<14} {kind:<12} {measurement['jsonmodem_ns']:>14,.0f} {measurement['orjson_ns']:>12,.0f} {measurement['ratio']:>7.2f}x", flush=True)
    if args.output:
        with open(args.output, "w") as output:
            json.dump(result, output, indent=2)
            output.write("\n")


if __name__ == "__main__":
    main()
