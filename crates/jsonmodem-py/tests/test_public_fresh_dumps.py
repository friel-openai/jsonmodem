"""Offline checks for first-call inputs, result lifetimes, and worker isolation."""

from collections import Counter
import gc
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

import bench_public_fresh_dumps as benchmark
import public_corpus as corpus
from test_public_corpus import document, make_library, manifest


def output_check(raw, encoded):
    return {
        "input_bytes": len(raw), "output_bytes": len(encoded),
        "output_sha256": hashlib.sha256(encoded).hexdigest(), "work_bytes": len(encoded),
    }


@pytest.fixture
def input_file(tmp_path):
    raw = b'{"a":[1,1.0,-0.0,true,null,"\\u2603"]}'
    (tmp_path / "small.json").write_bytes(raw)
    return document("small", raw), tmp_path, raw


def test_preparation_builds_equivalent_values_independently(input_file):
    _, _, raw = input_file
    left = benchmark.prepare_value(raw)
    right = benchmark.prepare_value(raw)
    corpus.assert_same(left, {"a": [1, 1.0, -0.0, True, None, "\u2603"]})
    corpus.assert_same(left, right)
    assert left is not right
    assert left["a"] is not right["a"]


@pytest.mark.parametrize("raw", [b"NaN", b"Infinity", b"[] []", b'"\xff"'])
def test_preparation_rejects_non_json_values(raw):
    with pytest.raises(ValueError):
        benchmark.prepare_value(raw)


def test_output_verification_checks_the_actual_bytes():
    expected = output_check(b"[ ]", b"[]")
    assert benchmark.verify_output(b"[]", 3, expected) == expected
    with pytest.raises(AssertionError, match="differs from correctness preflight"):
        benchmark.verify_output(b"{}", 3, expected)


@pytest.mark.parametrize("field,value", [
    ("input_bytes", 4), ("output_bytes", 3), ("work_bytes", 3), ("output_sha256", "0" * 64),
])
def test_output_verification_rejects_changed_preflight_fields(field, value):
    expected = output_check(b"[ ]", b"[]")
    expected[field] = value
    with pytest.raises(AssertionError, match="differs from correctness preflight"):
        benchmark.verify_output(b"[]", 3, expected)


@pytest.mark.parametrize("encoded", ["[]", bytearray(b"[]"), memoryview(b"[]"), None])
def test_output_verification_requires_exact_bytes(encoded):
    with pytest.raises(AssertionError, match="dumps must return bytes"):
        benchmark.verify_output(encoded, 2, output_check(b"[]", b"[]"))


def test_output_verification_rejects_a_bytes_subclass():
    class Encoded(bytes):
        """A bytes-like return value still differs from the required exact type."""

    with pytest.raises(AssertionError, match="dumps must return bytes"):
        benchmark.verify_output(Encoded(b"[]"), 2, output_check(b"[]", b"[]"))


@pytest.fixture
def protocol(monkeypatch):
    """Observe ownership and stopwatch order without retaining prepared objects."""
    def configure(failure=None):
        state = SimpleNamespace(
            events=[], live_inputs=set(), live_results=0, preparations=0,
            called_inputs=[], clock_reads=0, running=False, collections=0,
        )
        expected = {"verified": True}

        class Prepared:
            """Track parsed-value ownership through a serial number, not a reference."""

            def __init__(self, serial):
                self.serial = serial
                state.live_inputs.add(serial)

            def __del__(self):
                state.events.append(("drop-input", self.serial))
                state.live_inputs.remove(self.serial)

        class Result:
            """Make an overlapping result or timed destruction observable."""

            def __init__(self):
                state.live_results += 1

            def __del__(self):
                state.events.append(("drop-result", state.clock_reads))
                state.live_results -= 1

        def prepare(raw):
            assert raw == b"input"
            assert not state.live_inputs
            assert not state.live_results
            assert state.clock_reads == 0
            state.preparations += 1
            state.events.append(("prepare", state.preparations))
            if failure == "initial-prepare" and state.preparations == 1:
                raise ValueError("initial-prepare failed")
            if failure == "replacement-prepare" and state.preparations == 2:
                raise ValueError("replacement-prepare failed")
            return Prepared(state.preparations)

        def call(argument):
            assert not gc.isenabled()
            assert state.live_inputs == {argument.serial}
            assert state.live_results == 0
            label = "timed" if state.running else "warmup"
            state.events.append((label, argument.serial))
            state.called_inputs.append(argument.serial)
            if failure == label:
                raise ValueError(label + " failed")
            return Result()

        def clock():
            assert not gc.isenabled()
            state.clock_reads += 1
            assert len(state.live_inputs) == 1
            if state.clock_reads == 1:
                assert state.live_results == 0
                state.events.append(("start",))
                state.running = True
                return 1000
            assert state.clock_reads == 2
            assert state.live_results == 1
            state.events.append(("stop",))
            state.running = False
            return 1100

        def verify(result, input_bytes, checked):
            assert state.clock_reads == 2 and not state.running
            assert state.live_results == 1
            assert len(state.live_inputs) == 1
            assert not gc.isenabled()
            assert input_bytes == 5 and checked == expected
            state.events.append(("verify",))
            if failure == "verify":
                raise ValueError("verify failed")
            return expected

        def collect():
            assert state.clock_reads == 0
            state.collections += 1
            state.events.append(("collect",))

        monkeypatch.setattr(benchmark, "prepare_value", prepare)
        monkeypatch.setattr(benchmark, "verify_output", verify)
        monkeypatch.setattr(benchmark.time, "perf_counter_ns", clock)
        monkeypatch.setattr(benchmark.gc, "collect", collect)
        return state, call, expected

    return configure


@pytest.mark.parametrize("condition", benchmark.CONDITIONS)
@pytest.mark.parametrize("warmups", [0, 1, 10])
@pytest.mark.parametrize("enabled", [True, False])
def test_measure_has_one_timed_input_and_verifies_before_result_destruction(
    protocol, condition, warmups, enabled,
):
    state, call, expected = protocol()
    original = gc.isenabled()
    gc.enable() if enabled else gc.disable()
    try:
        result = benchmark.measure(call, b"input", condition, warmups, expected)
        assert gc.isenabled() == enabled
    finally:
        gc.enable() if original else gc.disable()
    preparation_count = 2 if condition == "fresh" and warmups else 1
    assert state.called_inputs == [1] * warmups + [preparation_count]
    assert state.preparations == preparation_count
    assert state.clock_reads == 2
    assert state.collections == 1
    assert state.live_inputs == set()
    assert state.live_results == 0
    start = state.events.index(("start",))
    stop = state.events.index(("stop",))
    verify = state.events.index(("verify",))
    assert state.events[start + 1:stop] == [("timed", preparation_count)]
    assert state.events[verify + 1:] == [("drop-result", 2), ("drop-input", preparation_count)]
    if preparation_count == 2:
        assert state.events.index(("drop-input", 1)) < state.events.index(("prepare", 2)) < start
    assert result["latency_ns"] == 100
    assert result["timed_calls"] == 1
    assert result["warmup_calls"] == warmups
    assert result["preparation_count"] == preparation_count
    assert result["returned_bytes_destruction_timed"] is False
    assert result["verification"] == expected
    assert result["clock"]["resolution_ns"] > 0


def test_zero_warmups_executes_the_same_procedure_in_both_conditions(protocol):
    events = []
    for condition in benchmark.CONDITIONS:
        state, call, expected = protocol()
        benchmark.measure(call, b"input", condition, 0, expected)
        events.append(state.events)
    assert events[0] == events[1]
    assert events[0] == [
        ("prepare", 1), ("collect",), ("start",), ("timed", 1),
        ("stop",), ("verify",), ("drop-result", 2), ("drop-input", 1),
    ]


@pytest.mark.parametrize("failure", ["initial-prepare", "replacement-prepare", "warmup", "timed", "verify"])
@pytest.mark.parametrize("enabled", [True, False])
def test_measure_failure_restores_gc(protocol, failure, enabled):
    state, call, expected = protocol(failure)
    original = gc.isenabled()
    gc.enable() if enabled else gc.disable()
    try:
        with pytest.raises(ValueError, match=failure + " failed"):
            benchmark.measure(call, b"input", "fresh", 1, expected)
        assert gc.isenabled() == enabled
    finally:
        gc.enable() if original else gc.disable()
    assert state.collections == (0 if failure == "initial-prepare" else 1)


@pytest.mark.parametrize("condition,warmups", [("unknown", 10), ("fresh", -1)])
def test_invalid_measurement_does_not_prepare_input(monkeypatch, condition, warmups):
    monkeypatch.setattr(benchmark, "prepare_value", lambda _: pytest.fail("unexpected preparation"))
    with pytest.raises(ValueError):
        benchmark.measure(lambda _: None, b"[]", condition, warmups, {})


def test_nonadvancing_clock_is_rejected_and_gc_restored(monkeypatch):
    monkeypatch.setattr(benchmark.time, "perf_counter_ns", lambda: 100)
    enabled = gc.isenabled()
    with pytest.raises(ValueError, match="clock did not advance"):
        benchmark.measure(lambda _: b"[]", b"[]", "fresh", 0, output_check(b"[]", b"[]"))
    assert gc.isenabled() == enabled


@pytest.fixture
def worker_input(monkeypatch):
    events = []
    metadata = {"version": "fixture", "executable_sha256": "f" * 64}
    expected = output_check(b"[]", b"[]")
    payload = {
        "expected_sources": benchmark.SOURCE_HASHES, "cpu": None,
        "library": {"name": "fixture", "module": "fixture", "pythonpath": []},
        "document": {"name": "fixture"}, "directory": "unused", "condition": "fresh",
        "warmups": 10, "expected_check": expected, "expected_metadata": metadata,
    }

    def imported(name):
        events.append("import")
        return SimpleNamespace(dumps=lambda _: b"[]")

    def read(*args):
        events.append("read")
        return b"[]"

    def measured(function, raw, condition, warmups, checked):
        assert raw == b"[]" and condition == "fresh" and warmups == 10
        assert checked == expected
        events.append("measure")
        return {"latency_ns": 100, "verification": checked}

    def fingerprint(*args):
        events.append("fingerprint")
        return metadata

    monkeypatch.setattr(benchmark.importlib, "import_module", imported)
    monkeypatch.setattr(benchmark, "read_document", read)
    monkeypatch.setattr(benchmark, "measure", measured)
    monkeypatch.setattr(benchmark, "module_metadata", fingerprint)
    return payload, events


def test_worker_reads_bytes_and_checks_fingerprints_after_measurement(worker_input):
    payload, events = worker_input
    result = benchmark.worker(payload)
    assert events == ["import", "read", "measure", "fingerprint"]
    assert result["metadata"] == payload["expected_metadata"]
    assert result["measurement"]["verification"] == payload["expected_check"]


def test_worker_rejects_build_or_environment_drift(worker_input):
    payload, events = worker_input
    payload["expected_metadata"] = {}
    with pytest.raises(ValueError, match="changed after verification"):
        benchmark.worker(payload)
    assert events[-1] == "fingerprint"


def test_worker_rejects_runner_drift_before_import():
    with pytest.raises(ValueError, match="benchmark source changed"):
        benchmark.worker({"expected_sources": {}})


def test_worker_requires_cpython_reference_counting(monkeypatch):
    monkeypatch.setattr(sys.implementation, "name", "another-interpreter")
    with pytest.raises(ValueError, match="require CPython"):
        benchmark.worker({"expected_sources": benchmark.SOURCE_HASHES})


def test_worker_sets_cpu_before_import(worker_input, monkeypatch):
    payload, events = worker_input
    payload["cpu"] = 8

    def affinity(pid, cpus):
        assert pid == 0 and cpus == {8}
        events.append("affinity")

    monkeypatch.setattr(benchmark.os, "sched_setaffinity", affinity, raising=False)
    benchmark.worker(payload)
    assert events[0:2] == ["affinity", "import"]


def test_worker_rejects_cpu_setting_without_os_support(worker_input, monkeypatch):
    payload, events = worker_input
    payload["cpu"] = 8
    monkeypatch.delattr(benchmark.os, "sched_setaffinity", raising=False)
    with pytest.raises(ValueError, match="CPU-affinity support"):
        benchmark.worker(payload)
    assert events == []


def test_worker_rechecks_document_bytes_before_measuring(worker_input, input_file, monkeypatch):
    payload, events = worker_input
    row, directory, raw = input_file
    payload.update(document=row, directory=str(directory))
    (directory / row["filename"]).write_bytes(raw.replace(b"true", b"null"))
    monkeypatch.setattr(benchmark, "read_document", corpus.read_document)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        benchmark.worker(payload)
    assert events == ["import"]


def test_child_starts_an_interpreter_for_every_request(monkeypatch):
    calls = []
    monkeypatch.setenv("PYTHONPATH", "/unused/ambient-module-directory")

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stderr="", stdout='{"ok": true}')

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    library = {"name": "fixture", "python": sys.executable}
    for condition in benchmark.CONDITIONS:
        for seed in (1729, 1730):
            assert benchmark.child(library, {"condition": condition}, seed, 17) == {"ok": True}
    assert len(calls) == 4
    for command, options in calls:
        assert command == [sys.executable, str(Path(benchmark.__file__).resolve()), "_worker"]
        assert options["timeout"] == 17
        assert options["env"]["PYTHONNOUSERSITE"] == "1"
        assert options["env"]["PYTHONHASHSEED"] in ("1729", "1730")
        assert "PYTHONPATH" not in options["env"]
        payload = json.loads(options["input"])
        assert payload["expected_sources"] == benchmark.SOURCE_HASHES
        assert payload["library"] == library


@pytest.mark.parametrize("status,stdout,message", [
    (9, "", "fresh worker exited 9: process failed"),
    (0, "not JSON", "Expecting value"),
])
def test_child_failure_returns_no_measurement(monkeypatch, status, stdout, message):
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=status, stderr="process failed", stdout=stdout,
    ))
    with pytest.raises(ValueError, match=message):
        benchmark.child({"name": "fixture", "python": sys.executable}, {"condition": "fresh"}, 1729, 30)


@pytest.mark.parametrize("drift", ["version", "source", "interpreter"])
def test_real_worker_rejects_changed_fingerprints(tmp_path, input_file, drift):
    row, directory, _ = input_file
    library = make_library(tmp_path, "fixture")
    verified = benchmark.verify_builds([library], {
        "documents": [row], "operations": ["dumps"], "directory": str(directory), "cpu": None,
    }, ["fixture"], 30)["fixture"]
    expected_metadata = dict(verified["metadata"])
    source = Path(library["pythonpath"][0]) / "corpus_test_adapter.py"
    if drift == "version":
        source.write_text(source.read_text() + "\n__version__ = 'changed'\n")
        message = "version.*expected"
    elif drift == "source":
        source.write_text(source.read_text() + "\n# Changed after preflight.\n")
        message = "changed after verification"
    else:
        expected_metadata["executable_sha256"] = "0" * 64
        message = "changed after verification"
    with pytest.raises(ValueError, match=message):
        benchmark.child(library, {
            "document": row, "directory": str(directory), "cpu": None,
            "condition": "fresh", "warmups": 1,
            "expected_check": verified["cases"]["dumps:small"],
            "expected_metadata": expected_metadata,
        }, 1729, 30)


@pytest.mark.parametrize("library_count", [1, 2, 3, 4])
def test_library_and_condition_positions_balance_independently(library_count):
    names = list(range(library_count))
    counts = Counter()
    for repeat in range(2 * library_count):
        libraries = benchmark.library_order(names, repeat)
        conditions = benchmark.condition_order(benchmark.CONDITIONS, repeat, library_count)
        for condition_position, condition in enumerate(conditions):
            for library_position, library in enumerate(libraries):
                counts[condition, condition_position, library, library_position] += 1
    assert len(counts) == 4 * library_count**2
    assert set(counts.values()) == {1}


def test_condition_order_preserves_the_requested_list_and_accepts_one_condition():
    conditions = ["fresh", "reused"]
    assert [benchmark.condition_order(conditions, repeat, 2) for repeat in range(4)] == [
        ["fresh", "reused"], ["fresh", "reused"], ["reused", "fresh"], ["reused", "fresh"],
    ]
    assert conditions == ["fresh", "reused"]
    assert benchmark.condition_order(["reused"], 3, 2) == ["reused"]


def test_summary_keeps_conditions_separate_and_uses_equal_document_weight():
    checks = {"dumps:a": {"work_bytes": 1000}, "dumps:b": {"work_bytes": 1000000}}
    runs = []
    for factor in (1, 20, 3):
        rows = {
            "ours": {"dumps:a": (100, 50), "dumps:b": (800, 100)},
            "reference": {"dumps:a": (200, 200), "dumps:b": (200, 200)},
            "control": {"dumps:a": (400, 400), "dumps:b": (400, 400)},
        }
        runs.append({"libraries": {
            name: {
                case: {
                    condition: {"latency_ns": factor * amount}
                    for condition, amount in zip(benchmark.CONDITIONS, values)
                }
                for case, values in cases.items()
            }
            for name, cases in rows.items()
        }})
    result = benchmark.summarize(runs, list(checks), checks, ["reference", "control"], benchmark.CONDITIONS)
    assert set(result["geomeans"]) == {"fresh", "reused"}
    assert result["geomeans"]["fresh"]["reference"]["ours"] == {
        "case_count": 2, "latency_ratio": pytest.approx(math.sqrt(2)),
        "faster_cases": 1, "slower_cases": 1,
    }
    assert result["geomeans"]["reused"]["reference"]["ours"]["latency_ratio"] == pytest.approx(math.sqrt(0.125))
    assert result["geomeans"]["fresh"]["control"]["ours"]["latency_ratio"] == pytest.approx(math.sqrt(0.5))
    row = result["cases"]["dumps:a"]["conditions"]["fresh"]
    assert row["measurements"]["ours"]["latency_ns"] == 300
    assert row["measurements"]["ours"]["throughput_MB_s"] == pytest.approx(1000 * 1000 / 300)
    assert row["measurements"]["ours"]["process_latencies_ns"] == [100, 2000, 300]
    assert row["ratios"]["reference"]["ours"]["paired_ratios"] == [0.5, 0.5, 0.5]


def test_summary_uses_the_ratio_of_process_medians():
    runs = [{"libraries": {
        name: {"dumps:a": {"fresh": {"latency_ns": value}}}
        for name, value in (("ours", left), ("reference", right))
    }} for left, right in ((1, 2), (20, 4), (3, 6))]
    result = benchmark.summarize(
        runs, ["dumps:a"], {"dumps:a": {"work_bytes": 2}}, ["reference"], ["fresh"],
    )
    row = result["cases"]["dumps:a"]["conditions"]["fresh"]
    assert row["ratios"]["reference"]["ours"]["latency_ratio"] == 0.75
    assert row["ratios"]["reference"]["ours"]["paired_ratios"] == [0.5, 5, 0.5]
    assert result["geomeans"]["fresh"]["reference"]["ours"]["latency_ratio"] == pytest.approx(0.75)


@pytest.fixture
def comparison(tmp_path, input_file, monkeypatch):
    row, directory, raw = input_file
    rows = [row, document("copy", raw), document("other", b'{"b":2}')]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest(rows)))
    libraries = [make_library(tmp_path, name) for name in ("ours", "reference")]
    libraries_path = tmp_path / "libraries.json"
    libraries_path.write_text(json.dumps({"libraries": libraries}))
    args = SimpleNamespace(
        manifest=manifest_path, directory=directory, cases=None, libraries=libraries_path,
        reference=["reference"], conditions=list(benchmark.CONDITIONS), cpu=None,
        repeats=4, warmups=10, timeout=30,
    )
    state = SimpleNamespace(checked=False, calls=[], drift=None)
    checks = {
        "dumps:" + source["name"]: {
            "input_bytes": source["size_bytes"], "output_bytes": 32, "work_bytes": 32,
            "output_sha256": source["sha256"],
        }
        for source in rows
    }
    metadata = {"version": "fixture"}

    def verify(libraries, payload, references, timeout):
        assert payload["operations"] == ["dumps"]
        state.checked = True
        selected = {"dumps:" + row["name"] for row in payload["documents"]}
        return {
            library["name"]: {
                "metadata": metadata,
                "cases": {case: checked for case, checked in checks.items() if case in selected},
            }
            for library in libraries
        }

    def child(library, payload, seed, timeout):
        assert state.checked
        assert "documents" not in payload and "operations" not in payload
        state.calls.append((library["name"], payload, seed))
        checked = dict(checks["dumps:" + payload["document"]["name"]])
        if state.drift == "output":
            checked["output_sha256"] = "0" * 64
        return {
            "metadata": {} if state.drift == "metadata" else metadata,
            "measurement": {"latency_ns": 100, "verification": checked},
        }

    monkeypatch.setattr(benchmark, "verify_builds", verify)
    monkeypatch.setattr(benchmark, "child", child)
    return args, state


def test_comparison_uses_one_document_and_condition_per_fresh_worker(comparison):
    args, state = comparison
    result = benchmark.compare(args)
    assert len(state.calls) == 32
    assert result["active_cases"] == ["dumps:small", "dumps:other"]
    assert result["duplicate_cases"] == {"dumps:copy": "dumps:small"}
    actual = []
    for name, payload, seed in state.calls:
        assert payload["warmups"] == 10
        assert payload["expected_metadata"] == {"version": "fixture"}
        assert payload["expected_check"] == result["verification"][name]["dumps:" + payload["document"]["name"]]
        actual.append((seed, payload["document"]["name"], payload["condition"], name))
    expected = []
    for run in result["runs"]:
        assert run["python_hash_seed"] == 1728 + run["repeat"]
        for name in run["document_order"]:
            if name == "copy":
                continue
            for condition in run["condition_order"]:
                for library in run["library_order"]:
                    expected.append((run["python_hash_seed"], name, condition, library))
    assert actual == expected
    assert [run["library_order"] for run in result["runs"]] == [
        ["ours", "reference"], ["reference", "ours"], ["ours", "reference"], ["reference", "ours"],
    ]
    assert [run["condition_order"] for run in result["runs"]] == [
        ["fresh", "reused"], ["fresh", "reused"], ["reused", "fresh"], ["reused", "fresh"],
    ]
    assert result["method"]["timed_calls_per_process"] == 1
    assert result["method"]["returned_bytes_destruction_timed"] is False
    assert str(args.directory) not in json.dumps(result)


def test_comparison_filters_cases_and_conditions(comparison):
    args, state = comparison
    args.cases, args.conditions = ["other"], ["fresh"]
    result = benchmark.compare(args)
    assert len(state.calls) == 8
    assert result["active_cases"] == ["dumps:other"]
    assert set(result["summary"]["geomeans"]) == {"fresh"}
    assert result["duplicate_cases"] == {}


def test_comparison_preflight_failure_starts_no_timed_workers(comparison, monkeypatch):
    args, state = comparison

    def fail(*arguments):
        raise ValueError("preflight failed")

    monkeypatch.setattr(benchmark, "verify_builds", fail)
    with pytest.raises(ValueError, match="preflight failed"):
        benchmark.compare(args)
    assert state.calls == []


@pytest.mark.parametrize("drift", ["metadata", "output"])
def test_comparison_rejects_worker_drift(comparison, drift):
    args, state = comparison
    state.drift = drift
    with pytest.raises(ValueError, match="changed after verification"):
        benchmark.compare(args)
    assert len(state.calls) == 1


def test_comparison_rejects_unknown_reference_before_preflight(comparison):
    args, state = comparison
    args.reference = ["not-configured"]
    with pytest.raises(ValueError, match="unknown reference libraries"):
        benchmark.compare(args)
    assert not state.checked and state.calls == []


def test_end_to_end_records_separate_reference_versions_and_portable_results(tmp_path):
    raw = b'{"key":[1,1.5,-0.0,true,null,"\\u2603"]}'
    (tmp_path / "small.json").write_bytes(raw)
    (tmp_path / "copy.json").write_bytes(raw)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest([document("small", raw), document("copy", raw)])))
    libraries = [make_library(tmp_path, name, version) for name, version in (
        ("ours", "fixture"), ("current", "3.12.0"), ("control", "3.11.9"),
    )]
    libraries[0].update(revision="a" * 40, wheel_sha256="b" * 64)
    libraries_path = tmp_path / "libraries.json"
    libraries_path.write_text(json.dumps({"libraries": libraries}))
    output = tmp_path / "result.json"
    command = [
        sys.executable, benchmark.__file__, "run", "--manifest", str(manifest_path),
        "--directory", str(tmp_path), "--libraries", str(libraries_path),
        "--reference", "current", "--reference", "control", "--output", str(output),
        "--repeats", "2", "--warmups", "2",
    ]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    text = output.read_text()
    result = json.loads(text)
    assert str(tmp_path) not in text and str(sys.executable) not in text
    assert result["benchmark"] == "public-corpus-fresh-dumps"
    assert result["active_cases"] == ["dumps:small"]
    assert result["duplicate_cases"] == {"dumps:copy": "dumps:small"}
    assert result["libraries"]["current"]["version"] == "3.12.0"
    assert result["libraries"]["control"]["version"] == "3.11.9"
    assert result["libraries"]["ours"]["declared_revision"] == "a" * 40
    assert result["libraries"]["ours"]["declared_wheel_sha256"] == "b" * 64
    for metadata in result["libraries"].values():
        assert metadata["executable_sha256"] == corpus.sha256_file(sys.executable)
        assert metadata["files"][0]["name"] == "corpus_test_adapter.py"
        assert len(metadata["files"][0]["sha256"]) == 64
        assert metadata["implementation"] == "CPython"
    assert result["fresh_dumps_runner_sha256"] == corpus.sha256_file(benchmark.__file__)
    assert result["method"]["returned_bytes_destruction_timed"] is False
    assert len(result["runs"]) == 2
    for run in result["runs"]:
        for name, cases in run["libraries"].items():
            for condition, measurement in cases["dumps:small"].items():
                assert measurement["latency_ns"] > 0
                assert measurement["timed_calls"] == 1 and measurement["warmup_calls"] == 2
                assert measurement["preparation_count"] == (2 if condition == "fresh" else 1)
                assert measurement["returned_bytes_destruction_timed"] is False
                assert measurement["verification"] == result["verification"][name]["dumps:small"]
                assert measurement["clock"]["monotonic"]
    assert set(result["summary"]["geomeans"]) == {"fresh", "reused"}
    for condition in result["summary"]["geomeans"].values():
        assert set(condition) == {"current", "control"}
    assert not list(tmp_path.glob(".result.json-*.tmp"))


def test_cli_failure_preserves_an_existing_result(tmp_path, input_file):
    row, directory, _ = input_file
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest([row])))
    library = make_library(tmp_path, "wrong-version")
    library["expected_version"] = "not-installed"
    libraries_path = tmp_path / "libraries.json"
    libraries_path.write_text(json.dumps({"libraries": [library]}))
    output = tmp_path / "result.json"
    output.write_text('{"keep": true}\n')
    command = [
        sys.executable, benchmark.__file__, "run", "--manifest", str(manifest_path),
        "--directory", str(directory), "--libraries", str(libraries_path),
        "--reference", "wrong-version", "--output", str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert completed.returncode != 0
    assert "expected 'not-installed'" in completed.stderr
    assert output.read_text() == '{"keep": true}\n'
    assert not list(tmp_path.glob(".result.json-*.tmp"))


@pytest.mark.parametrize("condition", benchmark.CONDITIONS)
def test_cli_checks_the_timed_output_after_exactly_ten_warmups(tmp_path, input_file, condition):
    row, directory, _ = input_file
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest([row])))
    library = make_library(tmp_path, "wrong-timed-output")
    source = Path(library["pythonpath"][0]) / "corpus_test_adapter.py"
    source.write_text(source.read_text() + (
        "\n_original_dumps = dumps\n"
        "_calls = 0\n"
        "def dumps(value):\n"
        "    global _calls\n"
        "    _calls += 1\n"
        "    if _calls == 11:\n"
        "        return b'{}'\n"
        "    return _original_dumps(value)\n"
    ))
    libraries_path = tmp_path / "libraries.json"
    libraries_path.write_text(json.dumps({"libraries": [library]}))
    output = tmp_path / "result.json"
    output.write_text('{"keep": true}\n')
    command = [
        sys.executable, benchmark.__file__, "run", "--manifest", str(manifest_path),
        "--directory", str(directory), "--libraries", str(libraries_path),
        "--reference", library["name"], "--conditions", condition,
        "--repeats", "1", "--output", str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert completed.returncode != 0
    assert "timed output differs from correctness preflight" in completed.stderr
    assert output.read_text() == '{"keep": true}\n'
    assert not list(tmp_path.glob(".result.json-*.tmp"))


@pytest.mark.parametrize("arguments,message", [
    (["--repeats", "0"], "repeats must be positive"),
    (["--warmups", "-1"], "warmups must be nonnegative"),
    (["--timeout", "nan"], "timeout must be finite and positive"),
    (["--timeout", "0"], "timeout must be finite and positive"),
    (["--cpu", "-1"], "cpu must be nonnegative"),
    (["--conditions", "fresh", "fresh"], "conditions must not repeat"),
])
def test_cli_rejects_invalid_measurement_settings_without_writing(
    tmp_path, monkeypatch, capsys, arguments, message,
):
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", [
        benchmark.__file__, "run", "--directory", str(tmp_path),
        "--libraries", str(tmp_path / "missing.json"), "--reference", "unused",
        "--output", str(output), *arguments,
    ])
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 2
    assert message in capsys.readouterr().err
    assert not output.exists()
