"""Pause concurrent callbacks while each encoder retains private output."""

from concurrent.futures import ThreadPoolExecutor
import datetime
import json
import threading

import pytest

import jsonmodem
import jsonmodem.portable as portable


@pytest.mark.parametrize("dumps", [jsonmodem.dumps, portable.dumps])
def test_callback_interleaving_does_not_share_output_or_cache(dumps):
    barrier = threading.Barrier(2, timeout=20)
    offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    dates = [datetime.datetime(2020, 1, 2, tzinfo=offset)] * 32

    def run(index):
        marker = object()
        retained = []
        for iteration in range(8):
            label = f"{index}:{iteration}"
            prefix = label + "x" * 4097

            def default(value):
                assert value is marker
                inner = dumps({"label": label, "text": "\u2603" * 1000})
                retained.append((inner, hash(inner)))
                # Waiting releases the GIL with an unfinished outer output.
                barrier.wait()
                return jsonmodem.Fragment(inner)

            result = dumps([prefix, marker, dates, label], default=default)
            decoded = json.loads(result)
            assert decoded == [
                prefix,
                {"label": label, "text": "\u2603" * 1000},
                ["2020-01-02T00:00:00+05:30"] * 32,
                label,
            ]
        for result, original_hash in retained:
            assert hash(result) == original_hash
            assert json.loads(result)["label"].startswith(f"{index}:")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, index) for index in range(2)]
        for future in futures:
            future.result(timeout=60)


@pytest.mark.parametrize("dumps", [jsonmodem.dumps, portable.dumps])
def test_input_mutation_while_callback_releases_gil_matches_owning_traversal(dumps):
    entered = threading.Event()
    changed = threading.Event()
    marker = object()
    values = list(range(129)) + [marker, {"old": 1}]

    def mutate():
        assert entered.wait(timeout=20)
        values[-1] = {"new": [1, 2, 3]}
        changed.set()

    def default(value):
        assert value is marker
        entered.set()
        assert changed.wait(timeout=20)
        return "callback"

    with ThreadPoolExecutor(max_workers=1) as pool:
        mutation = pool.submit(mutate)
        result = dumps(values, default=default)
        mutation.result(timeout=30)
    # The callback-aware encoder snapshots the input before invoking default.
    assert json.loads(result) == list(range(129)) + ["callback", {"old": 1}]
