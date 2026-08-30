"""Offline checks for corpus memory inputs, result lifetimes, and fresh workers."""

import gc
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

import bench_public_memory as benchmark
import public_corpus as corpus
from test_public_corpus import document, make_library, manifest


@pytest.fixture
def input_file(tmp_path):
    raw = b'{"a":[1,1.0,-0.0,true,null,"\\u2603"]}'
    (tmp_path / "small.json").write_bytes(raw)
    return document("small", raw), tmp_path, raw


def test_loads_worker_preparation_never_builds_a_reference_tree(input_file, monkeypatch):
    row, directory, raw = input_file
    monkeypatch.setattr(benchmark.json, "loads", lambda *args, **kwargs: pytest.fail("unexpected decode"))
    monkeypatch.setattr(corpus, "prepare_document", lambda *args: pytest.fail("reference tree retained"))
    assert benchmark.prepare_input(row, directory, "loads") == raw


def test_dumps_preparation_releases_original_bytes(input_file, monkeypatch):
    row, directory, raw = input_file
    released = []

    class InputBytes(bytes):
        """Observe source-byte destruction without retaining an extra reference."""

        def __del__(self):
            released.append(True)

    monkeypatch.setattr(benchmark, "read_document", lambda *args: InputBytes(raw))
    value = benchmark.prepare_input(row, directory, "dumps")
    corpus.assert_same(value, {"a": [1, 1.0, -0.0, True, None, "\u2603"]})
    assert released == [True]


def test_memory_preparation_still_checks_hashes(input_file):
    row, directory, raw = input_file
    (directory / row["filename"]).write_bytes(raw.replace(b"true", b"null"))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        benchmark.prepare_input(row, directory, "loads")


def test_memory_preparation_rejects_unknown_operation(input_file):
    row, directory, _ = input_file
    with pytest.raises(ValueError, match="unknown operation"):
        benchmark.prepare_input(row, directory, "invalid")


def test_discard_calls_does_not_retain_two_results():
    live, calls = [], []

    class Result:
        """One result may be live; another call must wait for its destruction."""

        def __init__(self):
            live.append(True)

        def __del__(self):
            live.pop()

    def call(argument):
        assert not live
        calls.append(argument)
        return Result()

    benchmark.discard_calls(call, "input", 10)
    assert calls == ["input"] * 10
    assert not live


@pytest.mark.skipif(sys.platform != "linux", reason="Linux RSS interface")
def test_rss_snapshot_normalizes_source_kib_to_bytes(monkeypatch):
    import resource

    monkeypatch.setattr(Path, "read_text", lambda self: "Name:\tpython\nVmRSS:\t17 kB\nVmHWM:\t19 kB\n")
    monkeypatch.setattr(resource, "getrusage", lambda who: SimpleNamespace(ru_maxrss=23))
    assert benchmark.rss_snapshot() == {
        "rss_bytes": 17 * 1024, "peak_rss_bytes": 19 * 1024, "ru_maxrss_bytes": 23 * 1024,
    }


@pytest.mark.skipif(sys.platform != "linux", reason="Linux RSS interface")
@pytest.mark.parametrize("status", [
    "VmRSS: 1 MB\nVmHWM: 2 kB\n", "VmRSS: -1 kB\nVmHWM: 2 kB\n", "VmRSS: 1 kB\n",
])
def test_rss_snapshot_rejects_missing_or_unexpected_units(monkeypatch, status):
    monkeypatch.setattr(Path, "read_text", lambda self: status)
    with pytest.raises(ValueError):
        benchmark.rss_snapshot()


@pytest.mark.parametrize("enabled", [True, False])
def test_rss_records_first_result_alive_and_restores_gc(monkeypatch, enabled):
    original = gc.isenabled()
    gc.enable() if enabled else gc.disable()
    state = SimpleNamespace(live=0, calls=0, snapshots=[], collections=0)

    class Result:
        """Track the lifetime of the value held during the first RSS snapshot."""

        def __init__(self):
            state.live += 1

        def __del__(self):
            state.live -= 1

    def collect():
        state.collections += 1

    def snapshot():
        assert not gc.isenabled()
        state.snapshots.append(state.live)
        return {"rss_bytes": 100 + state.live, "peak_rss_bytes": 500, "ru_maxrss_bytes": 600}

    def call(argument):
        assert not gc.isenabled()
        assert state.live == 0
        assert argument == "input"
        state.calls += 1
        return Result()

    monkeypatch.setattr(benchmark.gc, "collect", collect)
    monkeypatch.setattr(benchmark, "rss_snapshot", snapshot)
    try:
        result = benchmark.measure_rss(call, "input", 4, {"rss_bytes": 90})
        assert gc.isenabled() == enabled
    finally:
        gc.enable() if original else gc.disable()
    assert state.collections == 1
    assert state.calls == 4
    assert state.live == 0
    assert state.snapshots == [0, 1, 0, 0]
    assert result["calls"] == 4
    assert result["warmup_calls"] == 0
    assert result["peak_rss_bytes"] == 500
    assert result["prepared_rss_bytes"] == 100
    assert result["first_result_rss_bytes"] == 101
    assert result["snapshots"]["startup"] == {"rss_bytes": 90}


@pytest.fixture
def fake_memray(monkeypatch):
    state = SimpleNamespace(events=[], recording=False, flags=None)

    class Tracker:
        """Observe capture boundaries without loading or running a native profiler."""

        def __init__(self, filename, **flags):
            state.flags = flags
            Path(filename).write_bytes(b"test allocation capture")

        def __enter__(self):
            state.events.append("enter")
            state.recording = True

        def __exit__(self, *error):
            state.events.append("exit")
            state.recording = False

    def summary(profile):
        assert not state.recording
        state.events.append("summary")
        return {
            "allocation_requests": 10, "total_allocated_bytes": 200, "peak_live_bytes": 100,
            "python_allocator": "pymalloc", "trace_python_allocators": True,
            "native_traces": False, "file_format": "ALL_ALLOCATIONS",
        }

    monkeypatch.setitem(sys.modules, "memray", SimpleNamespace(
        __version__="test-profiler", Tracker=Tracker,
        FileFormat=SimpleNamespace(ALL_ALLOCATIONS="all"),
    ))
    monkeypatch.setattr(benchmark, "summarize_allocations", summary)
    monkeypatch.setattr(benchmark.gc, "collect", lambda: state.events.append("collect"))
    return state


@pytest.mark.parametrize("enabled", [True, False])
def test_memray_warmups_finish_before_tracking_without_another_gc(tmp_path, fake_memray, enabled):
    original = gc.isenabled()
    gc.enable() if enabled else gc.disable()

    def call(argument):
        assert not gc.isenabled()
        fake_memray.events.append("tracked" if fake_memray.recording else "warmup")

    try:
        result = benchmark.measure_memray(call, None, 3, 2, tmp_path / "capture.bin", None)
        assert gc.isenabled() == enabled
    finally:
        gc.enable() if original else gc.disable()
    assert fake_memray.events == ["collect", "warmup", "warmup", "enter", "tracked", "tracked", "tracked", "exit", "summary"]
    assert fake_memray.flags == {
        "trace_python_allocators": True, "native_traces": False, "file_format": "all",
    }
    assert result["memray_version"] == "test-profiler"
    assert result["calls"] == 3
    assert result["warmup_calls"] == 2
    assert result["allocation_requests"] == 10
    assert result["peak_live_bytes"] == 100
    assert result["capture"]["name"] == "capture.bin"
    assert result["capture"]["size_bytes"] == len(b"test allocation capture")
    assert str(tmp_path) not in json.dumps(result)


def test_memray_zero_warmups_means_first_call_is_tracked(tmp_path, fake_memray):
    def call(argument):
        assert fake_memray.recording
        fake_memray.events.append("tracked")

    benchmark.measure_memray(call, None, 1, 0, tmp_path / "capture.bin", "test-profiler")
    assert fake_memray.events == ["collect", "enter", "tracked", "exit", "summary"]


def test_memray_rejects_profiler_version_drift_before_calls(tmp_path, fake_memray):
    with pytest.raises(ValueError, match="Memray version.*expected"):
        benchmark.measure_memray(lambda _: pytest.fail("unexpected call"), None, 1, 1, tmp_path / "capture.bin", "other")
    assert fake_memray.events == []


@pytest.mark.parametrize("mode", ["rss", "memray"])
@pytest.mark.parametrize("enabled", [True, False])
def test_memory_call_failure_restores_gc(tmp_path, monkeypatch, fake_memray, mode, enabled):
    original = gc.isenabled()
    gc.enable() if enabled else gc.disable()

    def fail(argument):
        raise ValueError("call failed")

    monkeypatch.setattr(benchmark, "rss_snapshot", lambda: {})
    try:
        with pytest.raises(ValueError, match="call failed"):
            if mode == "rss":
                benchmark.measure_rss(fail, None, 1, {})
            else:
                benchmark.measure_memray(fail, None, 1, 0, tmp_path / "capture.bin", None)
        assert gc.isenabled() == enabled
    finally:
        gc.enable() if original else gc.disable()


@pytest.fixture
def rss_worker(monkeypatch):
    events = []
    metadata = {"version": "fixture"}
    payload = {
        "expected_sources": benchmark.SOURCE_HASHES, "cpu": None, "metric": "rss",
        "library": {"name": "fixture", "module": "fixture", "pythonpath": []},
        "document": {}, "directory": "unused", "operation": "loads", "rss_calls": 1,
        "expected_metadata": metadata,
    }

    def snapshot():
        events.append("startup")
        return {}

    def imported(name):
        events.append("import")
        return SimpleNamespace(loads=lambda _: None)

    def prepared(*args):
        events.append("prepare")
        return b"[]"

    def measured(*args):
        events.append("measure")
        return {"peak_rss_bytes": 100}

    def fingerprint(*args):
        events.append("fingerprint")
        return metadata

    monkeypatch.delitem(sys.modules, "memray", raising=False)
    monkeypatch.setattr(benchmark, "rss_snapshot", snapshot)
    monkeypatch.setattr(benchmark.importlib, "import_module", imported)
    monkeypatch.setattr(benchmark, "prepare_input", prepared)
    monkeypatch.setattr(benchmark, "measure_rss", measured)
    monkeypatch.setattr(benchmark, "module_metadata", fingerprint)
    return payload, events


def test_worker_fingerprints_are_created_after_memory_readings(rss_worker):
    payload, events = rss_worker
    result = benchmark.worker(payload)
    assert events == ["startup", "import", "prepare", "measure", "fingerprint"]
    assert result["measurement"]["peak_rss_bytes"] == 100


def test_worker_rejects_changed_build_after_measurement(rss_worker):
    payload, events = rss_worker
    payload["expected_metadata"] = {}
    with pytest.raises(ValueError, match="changed after verification"):
        benchmark.worker(payload)
    assert events[-2:] == ["measure", "fingerprint"]


def test_worker_rejects_changed_benchmark_code():
    with pytest.raises(ValueError, match="benchmark source changed"):
        benchmark.worker({"expected_sources": {}})


def test_rss_worker_rejects_accidental_memray_import(rss_worker, monkeypatch):
    payload, events = rss_worker
    monkeypatch.setitem(sys.modules, "memray", SimpleNamespace())
    with pytest.raises(ValueError, match="must not import Memray"):
        benchmark.worker(payload)
    assert "measure" not in events


def test_failed_child_does_not_return_a_measurement(monkeypatch):
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=9, stderr="process failed", stdout="",
    ))
    with pytest.raises(ValueError, match="rss worker exited 9: process failed"):
        benchmark.child({"name": "fixture", "python": sys.executable}, {"metric": "rss"}, 1729, 30)


def test_memory_summary_keeps_absolute_metrics_separate_and_does_not_average_ratios():
    runs = []
    for left, right in ((1, 2), (20, 4), (3, 6)):
        libraries = {}
        for name, amount in (("ours", left), ("reference", right)):
            libraries[name] = {"loads:a": {
                "memray": {
                    "allocation_requests": amount, "total_allocated_bytes": 0,
                    "peak_live_bytes": amount * 10,
                },
                "rss": {
                    "peak_rss_bytes": amount * 1000, "prepared_rss_bytes": amount * 100,
                    "first_result_rss_bytes": amount * 500,
                },
            }}
        runs.append({"libraries": libraries})
    result = benchmark.summarize(runs, ["loads:a"], {"loads:a": {"input_bytes": 2}}, ["reference"], ["rss", "memray"])
    assert set(result) == {"cases"}
    row = result["cases"]["loads:a"]
    assert row["memray"]["measurements"]["ours"]["allocation_requests"] == 3
    assert row["memray"]["measurements"]["ours"]["peak_live_bytes"] == 30
    assert row["memray"]["ratios"]["reference"]["ours"]["allocation_requests"] == 0.75
    assert row["memray"]["ratios"]["reference"]["ours"]["total_allocated_bytes"] is None
    assert row["rss"]["measurements"]["ours"]["peak_rss_bytes"] == 3000
    assert len(row["rss"]["measurements"]["ours"]["process_samples"]) == 3


@pytest.fixture
def comparison(tmp_path, input_file, monkeypatch):
    row, directory, raw = input_file
    rows = [row, document("copy", raw)]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest(rows)))
    libraries = [make_library(tmp_path, name) for name in ("ours", "reference")]
    libraries_path = tmp_path / "libraries.json"
    libraries_path.write_text(json.dumps({"libraries": libraries}))
    args = SimpleNamespace(
        manifest=manifest_path, directory=directory, cases=None, libraries=libraries_path,
        reference=["reference"], operations=["loads", "dumps"], metrics=["memray", "rss"],
        cpu=None, repeats=2, calls=1, warmups=10, rss_calls=10, memray_version=None,
        profiles=tmp_path / "profiles", timeout=30,
    )
    state = SimpleNamespace(checked=False, calls=[], profiler_versions={})
    checks = {}
    for source in rows:
        checks["loads:" + source["name"]] = {"input_bytes": len(raw), "work_bytes": len(raw)}
        checks["dumps:" + source["name"]] = {
            "input_bytes": len(raw), "output_bytes": 32, "work_bytes": 32,
            "output_sha256": "d" * 64,
        }

    def verify(libraries, payload, references, timeout):
        state.checked = True
        return {
            library["name"]: {"metadata": {"version": "fixture"}, "cases": checks}
            for library in libraries
        }

    def child(library, payload, seed, timeout):
        assert state.checked
        assert "documents" not in payload
        assert "operations" not in payload
        state.calls.append((library["name"], payload, seed))
        measurement = {field: 100 for field in benchmark.METRICS[payload["metric"]]}
        if payload["metric"] == "memray":
            measurement["memray_version"] = state.profiler_versions.get(library["name"], "fixture")
        return {"metadata": {"version": "fixture"}, "measurement": measurement}

    monkeypatch.setattr(benchmark, "verify_builds", verify)
    monkeypatch.setattr(benchmark, "child", child)
    return args, state


def test_comparison_uses_one_case_and_metric_per_worker_after_preflight(comparison):
    args, state = comparison
    result = benchmark.compare(args)
    assert len(state.calls) == 16
    assert result["active_cases"] == ["loads:small", "dumps:small"]
    assert result["duplicate_cases"] == {"loads:copy": "loads:small", "dumps:copy": "dumps:small"}
    assert result["memray_version"] == "fixture"
    for name, payload, seed in state.calls:
        assert payload["document"]["name"] == "small"
        assert payload["calls"] == 1
        assert payload["warmups"] == 10
        assert payload["rss_calls"] == 10
        assert payload["expected_metadata"] == {"version": "fixture"}
        assert seed in (1729, 1730)
        if payload["metric"] == "rss":
            assert payload["profile"] is None
        else:
            assert Path(payload["profile"]).parent.parent == args.profiles
    profiles = [payload["profile"] for _, payload, _ in state.calls if payload["profile"]]
    assert len(profiles) == len(set(profiles))
    assert result["runs"][0]["library_order"] == ["ours", "reference"]
    assert result["runs"][1]["library_order"] == ["reference", "ours"]


def test_comparison_preflight_failure_starts_no_memory_workers(comparison, monkeypatch):
    args, state = comparison

    def fail(*arguments):
        raise ValueError("preflight failed")

    monkeypatch.setattr(benchmark, "verify_builds", fail)
    with pytest.raises(ValueError, match="preflight failed"):
        benchmark.compare(args)
    assert state.calls == []
    assert not args.profiles.exists()


def test_comparison_rejects_mixed_profiler_versions(comparison):
    args, state = comparison
    state.profiler_versions = {"ours": "one-version", "reference": "other-version"}
    with pytest.raises(ValueError, match="Memray versions differ"):
        benchmark.compare(args)


@pytest.mark.skipif(sys.platform != "linux", reason="fresh-process Linux RSS comparison")
def test_rss_end_to_end_filters_duplicates_and_never_imports_memray(tmp_path):
    raw = b'{"key":[1,1.5,true,null,"value"]}'
    (tmp_path / "small.json").write_bytes(raw)
    (tmp_path / "copy.json").write_bytes(raw)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest([document("small", raw), document("copy", raw)])))
    libraries = [make_library(tmp_path, name, version) for name, version in (
        ("ours", "fixture"), ("current", "3.12.0"), ("control", "3.11.9"),
    )]
    for library in libraries:
        (Path(library["pythonpath"][0]) / "memray.py").write_text("raise AssertionError('RSS imported Memray')\n")
    libraries_path = tmp_path / "libraries.json"
    libraries_path.write_text(json.dumps({"libraries": libraries}))
    output = tmp_path / "result.json"
    command = [
        sys.executable, benchmark.__file__, "run", "--manifest", str(manifest_path),
        "--directory", str(tmp_path), "--libraries", str(libraries_path),
        "--reference", "current", "--reference", "control", "--output", str(output),
        "--metrics", "rss", "--repeats", "2", "--rss-calls", "2",
    ]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    text = output.read_text()
    result = json.loads(text)
    assert str(tmp_path) not in text
    assert result["memray_version"] is None
    assert result["active_cases"] == ["loads:small", "dumps:small"]
    assert result["duplicate_cases"] == {"loads:copy": "loads:small", "dumps:copy": "dumps:small"}
    assert len(result["runs"]) == 2
    assert result["runs"][0]["library_order"] == ["ours", "current", "control"]
    assert result["runs"][1]["library_order"] == ["current", "control", "ours"]
    assert result["libraries"]["current"]["version"] == "3.12.0"
    assert result["libraries"]["control"]["version"] == "3.11.9"
    for run in result["runs"]:
        for cases in run["libraries"].values():
            for case in cases.values():
                assert set(case) == {"rss"}
                row = case["rss"]
                assert row["calls"] == 2
                assert row["warmup_calls"] == 0
                assert row["peak_rss_bytes"] >= row["prepared_rss_bytes"] > 0
                assert list(row["snapshots"]) == [
                    "startup", "prepared", "first_result_alive", "first_result_released", "after_calls",
                ]
                assert row["peak_rss_bytes"] == row["snapshots"]["after_calls"]["peak_rss_bytes"]
    assert not list(tmp_path.glob("*.bin"))


@pytest.mark.skipif(sys.platform != "linux", reason="fresh-process Linux RSS comparison")
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
        "--reference", "wrong-version", "--metrics", "rss", "--output", str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert completed.returncode != 0
    assert "expected 'not-installed'" in completed.stderr
    assert output.read_text() == '{"keep": true}\n'
