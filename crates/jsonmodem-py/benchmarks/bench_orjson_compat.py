"""Compare jsonmodem's orjson-compatible frontend with orjson.

Run after ``maturin develop --release``:
``python benchmarks/bench_orjson_compat.py``.
"""

from __future__ import annotations

import json
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
}


def measure(function, argument, rounds=9, iterations=2_000):
    samples = []
    for _ in range(rounds):
        start = time.perf_counter_ns()
        for _ in range(iterations):
            function(argument)
        samples.append((time.perf_counter_ns() - start) / iterations)
    return statistics.median(samples)


def main():
    print(f"{'operation':<18} {'payload':<8} {'jsonmodem ns':>14} {'orjson ns':>12} {'ratio':>8}")
    for name, value in PAYLOADS.items():
        document = orjson.dumps(value)
        iterations = 2_000 if name == "small" else 100
        for operation, ours, theirs, argument in (
            ("loads", jsonmodem.loads, orjson.loads, document),
            ("dumps", jsonmodem.dumps, orjson.dumps, value),
        ):
            ours_ns = measure(ours, argument, iterations=iterations)
            theirs_ns = measure(theirs, argument, iterations=iterations)
            print(
                f"{operation:<18} {name:<8} {ours_ns:>14,.0f} {theirs_ns:>12,.0f} "
                f"{ours_ns / theirs_ns:>7.2f}x"
            )
            if operation == "loads":
                assert ours(argument) == theirs(argument)
            else:
                assert json.loads(ours(argument)) == json.loads(theirs(argument))


if __name__ == "__main__":
    main()
