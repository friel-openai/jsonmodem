"""Check bounded rejection inputs, exception lifetimes, and isolated measurements."""

import gc
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

import bench_rejections as benchmark


class Rejected(ValueError):
    """The only exception the fake decoder is allowed to raise successfully."""


@pytest.mark.parametrize("family", tuple(benchmark.FAMILIES))
def test_generated_inputs_have_exact_bounded_sizes_and_stable_hashes(family):
    parameters = benchmark.DEFAULT_DEPTHS if family == "depth_limit" else benchmark.DEFAULT_SIZES
    for parameter in parameters:
        raw = benchmark.build_input(family, parameter)
        expected_size = parameter * 2 + 1 if family == "depth_limit" else parameter
        assert type(raw) is bytes
        assert len(raw) == expected_size <= 1048577
        case = benchmark.describe_input(family, parameter, raw)
        assert case["sha256"] == hashlib.sha256(raw).hexdigest()
        assert benchmark.prepare_input(case) == raw
        assert case["depth"] == (parameter if family == "depth_limit" else None)


def test_default_selection_has_39_distinct_inputs():
    cases = benchmark.select_cases(None, benchmark.DEFAULT_SIZES, benchmark.DEFAULT_DEPTHS)
    assert len(cases) == 39
    assert len({case["name"] for case in cases}) == 39
    assert len({case["sha256"] for case in cases}) == 39
    assert max(case["input_bytes"] for case in cases) == 1048577


@pytest.mark.parametrize("family,parameter", [
    ("unknown", 64), ("syntax_early", 63), ("syntax_early", 1048577),
    ("unfinished_string", True), ("number_overflow", 64.0),
    ("depth_limit", 1024), ("depth_limit", 524289), ("depth_limit", "1025"),
])
def test_inputs_reject_unknown_families_and_out_of_range_parameters(family, parameter):
    with pytest.raises(ValueError):
        benchmark.build_input(family, parameter)


@pytest.mark.parametrize("families,sizes,depths", [
    ([], [64], [1025]), (["syntax_early", "syntax_early"], [64], [1025]),
    (["missing"], [64], [1025]), (None, [], [1025]), (None, [64, 64], [1025]),
    (None, [64], []), (None, [64], [1025, 1025]),
])
def test_selection_rejects_empty_duplicate_or_unknown_filters(families, sizes, depths):
    with pytest.raises(ValueError):
        benchmark.select_cases(families, sizes, depths)


def test_selection_applies_sizes_and_depths_independently():
    cases = benchmark.select_cases(["trailing_input", "depth_limit"], [4096, 64], [8192])
    assert [case["name"] for case in cases] == [
        "trailing_input_4096", "trailing_input_64", "depth_limit_8192",
    ]


@pytest.mark.parametrize("size", [64, 4096])
def test_syntax_errors_have_valid_repair_and_expected_position(size):
    early = benchmark.build_input("syntax_early", size)
    late = benchmark.build_input("syntax_late", size)
    valid = b"[" + early[1:]
    parsed = json.loads(valid)
    assert parsed == [{"k": 0}] * ((size - 1) // 8)
    last = len(late.rstrip()) - 1
    assert valid == late[:last] + b"]" + late[last + 1:]
    for raw, position in ((early, 0), (late, last)):
        with pytest.raises(json.JSONDecodeError) as captured:
            json.loads(raw)
        assert captured.value.pos == position
    trailing = benchmark.build_input("trailing_input", size)
    assert trailing.endswith(b" 0")
    assert json.loads(trailing[:-2]) == [{"k": 0}] * ((size - 3) // 8)
    with pytest.raises(json.JSONDecodeError) as captured:
        json.loads(trailing)
    assert captured.value.pos == size - 1


@pytest.mark.parametrize("family,repair", [
    ("unfinished_string", b'"'), ("unfinished_escape", b'\\"'),
    ("unfinished_unicode_escape", b'34"'),
])
def test_unfinished_strings_are_rejected_until_the_suffix_is_completed(family, repair):
    raw = benchmark.build_input(family, 64)
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
    assert type(json.loads(raw + repair)) is str


@pytest.mark.parametrize("family", ["utf8_early", "utf8_late"])
@pytest.mark.parametrize("size", [64, 4096])
def test_utf8_inputs_have_one_invalid_byte_and_an_otherwise_valid_string(family, size):
    raw = benchmark.build_input(family, size)
    assert raw.count(b"\xff") == 1
    with pytest.raises(UnicodeDecodeError) as captured:
        raw.decode("utf-8")
    assert captured.value.start == (1 if family == "utf8_early" else size - 2)
    assert type(json.loads(raw.replace(b"\xff", b"a"))) is str


def test_numeric_range_and_depth_cases_are_not_classified_as_syntax_errors():
    raw = benchmark.build_input("number_overflow", 64)
    assert json.loads(raw, parse_float=str) == raw.decode("ascii")
    assert float(raw) == float("inf")
    assert benchmark.FAMILIES["number_overflow"] == "numeric_range"
    raw = benchmark.build_input("depth_limit", 1025)
    assert raw == b"[" * 1025 + b"0" + b"]" * 1025
    assert benchmark.FAMILIES["depth_limit"] == "depth_limit"


@pytest.mark.parametrize("field,value", [
    ("sha256", "0" * 64), ("name", "changed"), ("rejection_category", "changed"),
    ("input_bytes", 65), ("depth", 1025),
])
def test_preparation_rejects_changed_descriptors(field, value):
    case = benchmark.select_cases(["syntax_early"], [64], [1025])[0]
    case[field] = value
    with pytest.raises(ValueError, match="descriptor or SHA-256 changed"):
        benchmark.prepare_input(case)


@pytest.mark.parametrize("module_name", ["jsonmodem", "orjson"])
@pytest.mark.parametrize("family", tuple(benchmark.FAMILIES))
def test_installed_libraries_reject_every_default_case(module_name, family):
    module = pytest.importorskip(module_name)
    parameters = benchmark.DEFAULT_DEPTHS if family == "depth_limit" else benchmark.DEFAULT_SIZES
    reject = benchmark.rejection_call(module.loads, module.JSONDecodeError)
    for parameter in parameters:
        raw = benchmark.build_input(family, parameter)
        checked = benchmark.verify_rejection(module, raw)
        assert checked["exception_type"]
        assert reject(raw) is None


def test_rejection_wrapper_does_not_accept_a_normal_return():
    reject = benchmark.rejection_call(lambda raw: None, Rejected)
    with pytest.raises(AssertionError, match="accepted"):
        reject(b"!")
    module = SimpleNamespace(loads=lambda raw: None, JSONDecodeError=Rejected)
    with pytest.raises(AssertionError, match="accepted"):
        benchmark.verify_rejection(module, b"!")


@pytest.mark.parametrize("error_type", [ValueError, MemoryError, RecursionError, TypeError])
def test_unexpected_exception_types_are_not_counted_as_success(error_type):
    def fail(raw):
        raise error_type("unexpected failure")

    reject = benchmark.rejection_call(fail, Rejected)
    with pytest.raises(error_type, match="unexpected failure"):
        reject(b"!")
    with pytest.raises(error_type, match="unexpected failure"):
        benchmark.verify_rejection(SimpleNamespace(loads=fail, JSONDecodeError=Rejected), b"!")


@pytest.mark.parametrize("error_type", [None, ValueError("instance"), str])
def test_rejection_wrapper_requires_an_exception_class(error_type):
    with pytest.raises(ValueError, match="exception class"):
        benchmark.rejection_call(lambda raw: None, error_type)


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="Checks reference-counted destruction")
def test_exception_and_owned_data_are_released_before_return_without_cyclic_gc():
    state = SimpleNamespace(live=0, destroyed=0)

    class OwnedData:
        """Observe the lifetime of data retained only by a decoder exception."""

        def __del__(self):
            state.destroyed += 1

    class DecodeError(ValueError):
        """Track expected exceptions without retaining them in the test."""

        def __init__(self):
            state.live += 1
            self.doc = OwnedData()

        def __del__(self):
            state.live -= 1

    def fail(raw):
        assert state.live == 0
        raise DecodeError()

    reject = benchmark.rejection_call(fail, DecodeError)
    original = gc.isenabled()
    gc.disable()
    try:
        for count in range(1, 4):
            assert reject(b"!") is None
            assert state.live == 0
            assert state.destroyed == count
    finally:
        gc.enable() if original else gc.disable()


@pytest.fixture
def fake_worker(monkeypatch):
    events = []
    monkeypatch.delitem(sys.modules, "memray", raising=False)

    def fail(raw):
        events.append(("loads", raw))
        raise Rejected("expected")

    module = SimpleNamespace(loads=fail, JSONDecodeError=Rejected)
    metadata = {"module": "test_decoder", "version": "test-version"}
    monkeypatch.setattr(benchmark.importlib, "import_module", lambda name: module)
    monkeypatch.setattr(benchmark, "module_metadata", lambda library, module: dict(metadata))
    monkeypatch.setattr(benchmark, "memray_metadata", lambda version: {"version": version, "files": []})
    case = benchmark.select_cases(["syntax_early"], [64], [1025])[0]
    payload = {
        "expected_sources": benchmark.SOURCE_HASHES,
        "library": {"name": "test", "module": "test_decoder", "pythonpath": []},
        "cpu": None, "mode": "measure", "metric": "latency", "case": case,
        "expected_metadata": dict(metadata),
        "seconds": 0.03, "samples": 3, "latency_warmups": 3,
        "memray_calls": 1, "memray_warmups": 10, "profile": "test.bin", "memray_version": "1.20.0",
    }
    return payload, events


def test_worker_reuses_latency_helper_and_retains_all_samples(fake_worker, monkeypatch):
    payload, events = fake_worker
    samples = {"iterations_per_sample": 4, "sample_elapsed_ns": [40, 48, 44],
               "sample_latency_ns": [10, 12, 11], "median_latency_ns": 11}

    def measure(function, raw, seconds, count, warmups):
        assert (seconds, count, warmups) == (0.03, 3, 3)
        assert raw == benchmark.build_input("syntax_early", 64)
        assert function(raw) is None
        return samples

    monkeypatch.setattr(benchmark, "measure", measure)
    monkeypatch.setattr(benchmark, "measure_memray", lambda *args: pytest.fail("unexpected profiler"))
    result = benchmark.worker(payload)
    assert result["measurement"] == samples
    assert len(events) == 1


def test_worker_reuses_allocation_helper_with_explicit_warmup_and_call_counts(fake_worker, monkeypatch):
    payload, events = fake_worker
    payload["metric"] = "memray"

    def measure(function, raw, calls, warmups, profile, version):
        assert (calls, warmups, profile, version) == (1, 10, Path("test.bin"), "1.20.0")
        assert function(raw) is None
        return {"allocation_requests": 7, "total_allocated_bytes": 64, "peak_live_bytes": 48}

    monkeypatch.setattr(benchmark, "measure_memray", measure)
    monkeypatch.setattr(benchmark, "measure", lambda *args: pytest.fail("unexpected timing"))
    assert benchmark.worker(payload)["measurement"]["allocation_requests"] == 7
    assert len(events) == 1


def test_worker_preflight_checks_every_hash_and_rejection_without_measuring(fake_worker, monkeypatch):
    payload, events = fake_worker
    payload.update(mode="verify", cases=benchmark.select_cases(["syntax_early", "syntax_late"], [64, 4096], [1025]))
    monkeypatch.setattr(benchmark, "measure", lambda *args: pytest.fail("unexpected timing"))
    monkeypatch.setattr(benchmark, "measure_memray", lambda *args: pytest.fail("unexpected profiler"))
    checks = benchmark.worker(payload)["checks"]
    assert list(checks) == [case["name"] for case in payload["cases"]]
    assert len(events) == 4
    for case in payload["cases"]:
        assert checks[case["name"]] == {
            "exception_type": f"{Rejected.__module__}.{Rejected.__qualname__}",
            "input_sha256": case["sha256"],
        }


def test_worker_rejects_source_drift_before_importing():
    with pytest.raises(ValueError, match="benchmark source changed"):
        benchmark.worker({"expected_sources": {}})


def test_worker_rejects_build_drift_before_calling_loads(fake_worker):
    payload, events = fake_worker
    payload["expected_metadata"] = {}
    with pytest.raises(ValueError, match="changed after verification"):
        benchmark.worker(payload)
    assert not events


def test_worker_rejects_changed_input_before_calling_loads(fake_worker, monkeypatch):
    payload, events = fake_worker
    payload["case"]["sha256"] = "0" * 64
    monkeypatch.setattr(benchmark, "measure", lambda *args: pytest.fail("unexpected timing"))
    with pytest.raises(ValueError, match="descriptor or SHA-256 changed"):
        benchmark.worker(payload)
    assert not events


@pytest.mark.parametrize("changed", ["source", "library"])
def test_worker_rejects_drift_during_measurement(fake_worker, monkeypatch, changed):
    payload, _ = fake_worker

    def measure(*args):
        if changed == "source":
            monkeypatch.setattr(benchmark, "source_hashes", lambda: {})
        else:
            monkeypatch.setattr(benchmark, "module_metadata", lambda *args: {})
        return {"median_latency_ns": 1}

    monkeypatch.setattr(benchmark, "measure", measure)
    with pytest.raises(ValueError, match="changed during the worker"):
        benchmark.worker(payload)


@pytest.mark.parametrize("when", ["before", "during"])
def test_worker_rejects_profiler_drift(fake_worker, monkeypatch, when):
    payload, _ = fake_worker
    payload["metric"] = "memray"
    if when == "before":
        payload["expected_memray_metadata"] = {}
        monkeypatch.setattr(benchmark, "measure_memray", lambda *args: pytest.fail("unexpected capture"))
    else:
        def measure(*args):
            monkeypatch.setattr(benchmark, "memray_metadata", lambda version: {})
            return {}
        monkeypatch.setattr(benchmark, "measure_memray", measure)
    with pytest.raises(ValueError, match="Memray build or environment changed"):
        benchmark.worker(payload)


@pytest.mark.parametrize("when", ["before", "during"])
def test_latency_workers_reject_profiler_imports(fake_worker, monkeypatch, when):
    payload, _ = fake_worker
    if when == "before":
        monkeypatch.setitem(sys.modules, "memray", SimpleNamespace())
        monkeypatch.setattr(benchmark, "measure", lambda *args: pytest.fail("unexpected timing"))
    else:
        def measure(*args):
            monkeypatch.setitem(sys.modules, "memray", SimpleNamespace())
            return {}
        monkeypatch.setattr(benchmark, "measure", measure)
    with pytest.raises(ValueError, match="latency workers must not import Memray"):
        benchmark.worker(payload)


@pytest.fixture
def comparison(tmp_path, monkeypatch):
    libraries = [{"name": "jsonmodem_baseline"}, {"name": "orjson_3119"}]
    monkeypatch.setattr(benchmark, "load_libraries", lambda path: libraries)
    args = SimpleNamespace(
        cases=["syntax_early", "depth_limit"], sizes=[64, 4096], depths=[1025],
        libraries=tmp_path / "libraries.json", metrics=["latency", "memray"],
        cpu=None, repeats=3, samples=3, seconds=0.03, latency_warmups=3,
        memray_calls=1, memray_warmups=10, memray_version="1.20.0",
        profiles=tmp_path / "profiles", timeout=30,
    )
    calls = []

    def child(library, payload, hash_seed, timeout):
        calls.append((library["name"], payload, hash_seed, timeout))
        metadata = {"module": library["name"], "version": "test-version"}
        profiler = {"version": "1.20.0", "files": []}
        if payload["mode"] == "verify":
            return {"metadata": metadata, "memray_metadata": profiler, "checks": {
                case["name"]: {"exception_type": "json.JSONDecodeError", "input_sha256": case["sha256"]}
                for case in payload["cases"]
            }}
        value = hash_seed - 1728 + (10 if library["name"] == "jsonmodem_baseline" else 0)
        if payload["metric"] == "latency":
            measurement = {
                "iterations_per_sample": 1, "sample_elapsed_ns": [value, value * 3, value * 2],
                "sample_latency_ns": [value, value * 3, value * 2], "median_latency_ns": value * 2,
            }
        else:
            measurement = {
                "allocation_requests": value, "total_allocated_bytes": value * 100,
                "peak_live_bytes": value * 50, "memray_version": "1.20.0",
                "calls": 1, "warmup_calls": 10,
                "capture": {"name": Path(payload["profile"]).name, "sha256": "1" * 64, "size_bytes": 9},
            }
        return {
            "metadata": metadata, "measurement": measurement,
            "memray_metadata": profiler if payload["metric"] == "memray" else None,
        }

    monkeypatch.setattr(benchmark, "child", child)
    return args, calls


def test_comparison_preflights_both_libraries_then_uses_one_worker_per_measurement(comparison, tmp_path):
    args, calls = comparison
    result = benchmark.compare(args)
    assert [payload["mode"] for _, payload, _, _ in calls[:2]] == ["verify", "verify"]
    assert all(payload["mode"] == "measure" for _, payload, _, _ in calls[2:])
    assert len(calls) == 2 + 3 * 2 * 3 * 2
    assert [run["library_order"] for run in result["runs"]] == [
        ["jsonmodem_baseline", "orjson_3119"], ["orjson_3119", "jsonmodem_baseline"],
        ["jsonmodem_baseline", "orjson_3119"],
    ]
    for repeat, run in enumerate(result["runs"]):
        order = [case["name"] for case in result["cases"]]
        random.Random(1729 + repeat).shuffle(order)
        assert run["case_order"] == order
        assert run["python_hash_seed"] == 1729 + repeat
        assert run["metric_order"] == ["latency", "memray"]
    summary = result["summary"]["cases"]["syntax_early_64"]
    assert summary["latency"]["jsonmodem_baseline"]["median_latency_ns"] == 24
    assert summary["latency"]["orjson_3119"]["median_latency_ns"] == 4
    assert summary["memray"]["orjson_3119"] == {
        "allocation_requests": 2, "total_allocated_bytes": 200, "peak_live_bytes": 100,
    }
    assert result["runs"][0]["libraries"]["orjson_3119"]["syntax_early_64"]["latency"]["sample_elapsed_ns"] == [1, 3, 2]
    assert set(result["summary"]) == {"cases"}
    assert str(tmp_path) not in json.dumps(result)
    assert "throughput" not in result["summary"]
    assert "geomean" not in result["summary"]


def test_preflight_failure_prevents_all_measurements_and_capture_creation(comparison, monkeypatch):
    args, calls = comparison
    original = benchmark.child

    def fail(library, payload, seed, timeout):
        assert payload["mode"] == "verify"
        if library["name"] == "orjson_3119":
            raise AssertionError("unexpected acceptance")
        return original(library, payload, seed, timeout)

    monkeypatch.setattr(benchmark, "child", fail)
    with pytest.raises(AssertionError, match="unexpected acceptance"):
        benchmark.compare(args)
    assert len(calls) == 1
    assert not args.profiles.exists()


@pytest.mark.parametrize("changed", ["metadata", "memray_version", "memray_metadata"])
def test_parent_rejects_changed_worker_metadata(comparison, monkeypatch, changed):
    args, _ = comparison
    original = benchmark.child

    def drift(library, payload, seed, timeout):
        result = original(library, payload, seed, timeout)
        if payload["mode"] == "measure":
            if changed == "metadata":
                result["metadata"] = {}
            elif changed == "memray_version" and payload["metric"] == "memray":
                result["measurement"]["memray_version"] = "changed"
            elif changed == "memray_metadata":
                result["memray_metadata"] = {}
        return result

    monkeypatch.setattr(benchmark, "child", drift)
    with pytest.raises(ValueError, match="changed after verification"):
        benchmark.compare(args)


def test_child_uses_configured_interpreter_clean_environment_and_timeout(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "unwanted")
    monkeypatch.setenv("PYTHONHOME", "unwanted")
    seen = []

    def run(command, **options):
        seen.append((command, options))
        return SimpleNamespace(returncode=0, stdout='{"measurement": {}}', stderr="")

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    library = {"name": "test", "python": "configured-python"}
    benchmark.child(library, {"mode": "verify", "cpu": None}, 1730, 17)
    command, options = seen[0]
    assert command == ["configured-python", str(Path(benchmark.__file__).resolve()), "_worker"]
    assert options["timeout"] == 17
    assert options["env"]["PYTHONHASHSEED"] == "1730"
    assert options["env"]["PYTHONNOUSERSITE"] == "1"
    assert options["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "PYTHONPATH" not in options["env"]
    assert "PYTHONHOME" not in options["env"]
    assert json.loads(options["input"])["expected_sources"] == benchmark.SOURCE_HASHES


def test_child_fails_on_nonzero_exit_without_trying_to_use_partial_output(monkeypatch):
    monkeypatch.setattr(benchmark.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stdout='{"measurement": {}}', stderr="unexpected exception",
    ))
    with pytest.raises(ValueError, match="worker exited 1.*unexpected exception"):
        benchmark.child({"name": "test", "python": sys.executable}, {"mode": "measure"}, 1729, 30)


def test_child_timeout_is_not_silently_dropped(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("worker", 3)

    monkeypatch.setattr(benchmark.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        benchmark.child({"name": "test", "python": sys.executable}, {"mode": "measure"}, 1729, 3)


@pytest.mark.parametrize("options", [
    ["--repeats", "0"], ["--samples", "0"], ["--memray-calls", "0"],
    ["--latency-warmups", "-1"], ["--memray-warmups", "-1"],
    ["--seconds", "nan"], ["--seconds", "inf"], ["--timeout", "0"], ["--cpu", "-1"],
    ["--sizes", "63"], ["--sizes", "1048577"], ["--depths", "1024"],
    ["--cases", "syntax_early", "syntax_early"], ["--metrics", "latency", "latency"],
])
def test_cli_rejects_invalid_settings_before_loading_libraries(tmp_path, monkeypatch, options):
    monkeypatch.setattr(sys, "argv", [
        benchmark.__file__, "run", "--libraries", "unused.json", "--metrics", "latency",
        "--output", str(tmp_path / "result.json"), *options,
    ])
    monkeypatch.setattr(benchmark, "load_libraries", lambda path: pytest.fail("unexpected library configuration"))
    with pytest.raises(SystemExit) as captured:
        benchmark.main()
    assert captured.value.code != 0


def test_cli_refuses_to_replace_an_existing_result(tmp_path, monkeypatch):
    output = tmp_path / "result.json"
    output.write_text("existing result\n")
    monkeypatch.setattr(sys, "argv", [
        benchmark.__file__, "run", "--libraries", "unused.json", "--metrics", "latency",
        "--output", str(output),
    ])
    monkeypatch.setattr(benchmark, "compare", lambda args: pytest.fail("unexpected comparison"))
    with pytest.raises(SystemExit) as captured:
        benchmark.main()
    assert captured.value.code != 0
    assert output.read_text() == "existing result\n"


def test_cli_latency_only_results_are_portable_and_preserve_samples(tmp_path):
    libraries = []
    for name in ("first", "second"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "rejection_test_adapter.py").write_text(
            "import json\n__version__ = 'test-version'\n"
            "loads = json.loads\nJSONDecodeError = json.JSONDecodeError\n"
        )
        libraries.append({
            "name": name, "module": "rejection_test_adapter", "python": sys.executable,
            "pythonpath": [str(directory)], "expected_version": "test-version",
        })
    configuration = tmp_path / "libraries.json"
    configuration.write_text(json.dumps({"libraries": libraries}))
    output = tmp_path / "result.json"
    subprocess.run([
        sys.executable, benchmark.__file__, "run", "--libraries", str(configuration),
        "--cases", "syntax_early", "unfinished_escape", "--sizes", "64",
        "--metrics", "latency", "--repeats", "2", "--samples", "3", "--seconds", "0.00001",
        "--latency-warmups", "0", "--output", str(output),
    ], check=True, capture_output=True, text=True, timeout=30)
    text = output.read_text()
    result = json.loads(text)
    assert str(tmp_path) not in text
    assert result["benchmark"] == "complete-load-rejections"
    assert len(result["runs"]) == 2
    assert len(result["cases"]) == 2
    assert result["rejection_runner_sha256"] == benchmark.SOURCE_HASHES["rejection_runner_sha256"]
    for library in result["libraries"].values():
        assert library["files"][0]["name"] == "rejection_test_adapter.py"
        assert len(library["files"][0]["sha256"]) == 64
        assert len(library["executable_sha256"]) == 64
    for run in result["runs"]:
        for library in run["libraries"].values():
            for case in library.values():
                assert set(case) == {"latency"}
                assert len(case["latency"]["sample_elapsed_ns"]) == 3
                assert case["latency"]["iterations_per_sample"] > 0
