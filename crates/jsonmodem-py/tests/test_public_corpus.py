"""Offline checks for corpus integrity, correctness, timing, and aggregation."""

import gc
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))

import bench_public_corpus as benchmark
import public_corpus as corpus


def document(name, raw):
    return {
        "name": name, "filename": name + ".json",
        "description": "Locally generated test data.",
        "url": "https://example.invalid/" + name + ".json",
        "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "terms": "test-data", "suite": "test-suite",
    }


def manifest(documents):
    return {
        "schema_version": 1, "name": "test-corpus",
        "terms": {"test-data": {"license": "MIT"}},
        "suites": {"test-suite": {"description": "Locally generated tests"}},
        "documents": documents,
    }


def test_default_manifest_is_pinned_and_complete():
    value = corpus.load_manifest()
    assert len(value["documents"]) == 18
    assert sum(row["size_bytes"] for row in value["documents"]) == 92389797
    assert len({row["sha256"] for row in value["documents"]}) == 18
    for row in value["documents"]:
        revision = row["url"].split("/")[5]
        assert len(revision) == 40
        assert all(character in "0123456789abcdef" for character in revision)
    assert value["terms"]["upstream-data-terms"]["license"] is None


@pytest.mark.parametrize("field,value", [
    ("name", "../escape"), ("name", ""), ("filename", "../escape.json"),
    ("filename", "different.json"), ("size_bytes", True), ("size_bytes", 0),
    ("sha256", "0" * 63), ("sha256", "x" * 64),
    ("url", "http://example.invalid/a.json"),
    ("url", "https://user:password@example.invalid/a.json"),
    ("terms", "missing"), ("suite", "missing"),
])
def test_manifest_rejects_invalid_documents(tmp_path, field, value):
    row = document("a", b"[]")
    row[field] = value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest([row])))
    with pytest.raises(ValueError):
        corpus.load_manifest(path)


def test_manifest_rejects_duplicate_names(tmp_path):
    row = document("a", b"[]")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest([row, row])))
    with pytest.raises(ValueError, match="duplicate document name"):
        corpus.load_manifest(path)


@pytest.mark.parametrize("value", [[], None, {"schema_version": 1}, manifest([None])])
def test_manifest_rejects_wrong_structure(tmp_path, value):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        corpus.load_manifest(path)


def test_filters_are_exact_and_keep_manifest_order():
    rows = [document("first", b"[]"), document("second", b"{}")]
    value = manifest(rows)
    assert corpus.select_documents(value, ["second", "first"]) == rows
    assert corpus.select_documents(value, ["first", "first"]) == rows[:1]
    with pytest.raises(ValueError, match="unknown corpus cases"):
        corpus.select_documents(value, ["typo"])
    with pytest.raises(ValueError, match="at least one"):
        corpus.select_documents(value, [])


@pytest.mark.parametrize("replacement,message", [(b"[0]", "size mismatch"), (b"{}", "SHA-256 mismatch")])
def test_read_document_rejects_changes(tmp_path, replacement, message):
    row = document("a", b"[]")
    (tmp_path / "a.json").write_bytes(replacement)
    with pytest.raises(ValueError, match=message):
        corpus.read_document(row, tmp_path)


def test_prepare_document_preserves_original_bytes_and_types(tmp_path):
    raw = b'{ "a": [1, 1.0, -0.0, true, null, "\\u2603"] }\n'
    row = document("a", raw)
    (tmp_path / "a.json").write_bytes(raw)
    loaded, value = corpus.prepare_document(row, tmp_path)
    assert loaded == raw
    corpus.assert_same(value, {"a": [1, 1.0, -0.0, True, None, "\u2603"]})


@pytest.mark.parametrize("raw", [b"NaN", b"Infinity", b"[] []", b'"\xff"'])
def test_prepare_rejects_non_json_inputs(tmp_path, raw):
    row = document("a", raw)
    (tmp_path / "a.json").write_bytes(raw)
    with pytest.raises(ValueError):
        corpus.prepare_document(row, tmp_path)


class Response(io.BytesIO):
    """A finite HTTPS response for download tests, with no network access."""

    def geturl(self):
        return "https://example.invalid/a.json"


def test_fetch_verifies_and_reuses_cache(tmp_path, monkeypatch):
    row = document("a", b"[]")
    monkeypatch.setattr(corpus.urllib.request, "urlopen", lambda *args, **kwargs: Response(b"[]"))
    assert corpus.fetch_document(row, tmp_path) == "downloaded"
    assert (tmp_path / "a.json").read_bytes() == b"[]"
    monkeypatch.setattr(corpus.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("unexpected download"))
    assert corpus.fetch_document(row, tmp_path) == "cached"
    (tmp_path / "a.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        corpus.fetch_document(row, tmp_path)
    assert (tmp_path / "a.json").read_bytes() == b"{}"


@pytest.mark.parametrize("raw", [b"[0]", b"[", b"{}"])
def test_failed_download_leaves_no_file(tmp_path, monkeypatch, raw):
    monkeypatch.setattr(corpus.urllib.request, "urlopen", lambda *args, **kwargs: Response(raw))
    with pytest.raises(ValueError, match="mismatch"):
        corpus.fetch_document(document("a", b"[]"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_rejects_http_redirect(tmp_path, monkeypatch):
    response = Response(b"[]")
    response.geturl = lambda: "http://example.invalid/a.json"
    monkeypatch.setattr(corpus.urllib.request, "urlopen", lambda *args, **kwargs: response)
    with pytest.raises(ValueError, match="away from HTTPS"):
        corpus.fetch_document(document("a", b"[]"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_cached_symlink_is_not_read(tmp_path):
    target = tmp_path / "other.json"
    target.write_bytes(b"[]")
    (tmp_path / "a.json").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        corpus.read_document(document("a", b"[]"), tmp_path)


@pytest.mark.parametrize("actual,expected", [
    (True, 1), (1.0, 1), (0.0, -0.0), (float("inf"), float("inf")),
    ([1], [1, 2]), ([False], [0]), ({"b": 2, "a": 1}, {"a": 1, "b": 2}),
    ("changed", "original"), ((1,), [1]), (iter([1]), [1]),
])
def test_correctness_rejects_incomplete_or_inexact_results(actual, expected):
    with pytest.raises(AssertionError):
        corpus.assert_same(actual, expected)


def test_correctness_walk_does_not_use_python_recursion():
    left, right = [], []
    for _ in range(2000):
        left, right = [left], [right]
    corpus.assert_same(left, right)


def test_serializer_cannot_mutate_correctness_reference():
    def dumps(value):
        value["a"] = 2
        return b'{"a":2}'

    with pytest.raises(AssertionError, match="scalar"):
        benchmark.verify_operation(SimpleNamespace(dumps=dumps), "dumps", b'{"a":1}', {"a": 1})


def test_serializer_must_return_bytes():
    with pytest.raises(AssertionError, match="return bytes"):
        benchmark.verify_operation(SimpleNamespace(dumps=json.dumps), "dumps", b"[]", [])


def test_deduplication_is_per_operation():
    rows = [document("a", b"[]"), document("copy", b"[]"), document("pretty", b"[ ]")]
    checks = {"dumps:" + row["name"]: {"output_sha256": "same"} for row in rows}
    active, aliases = benchmark.unique_cases(rows, ["loads", "dumps"], checks)
    assert active == ["loads:a", "dumps:a", "loads:pretty"]
    assert aliases == {"loads:copy": "loads:a", "dumps:copy": "dumps:a", "dumps:pretty": "dumps:a"}


def test_process_order_alternates_or_balances_positions():
    assert [benchmark.library_order(["a", "b"], i) for i in range(4)] == [
        ["a", "b"], ["b", "a"], ["a", "b"], ["b", "a"],
    ]
    orders = [benchmark.library_order(["a", "b", "c"], i) for i in range(6)]
    for column in zip(*orders):
        assert sorted(column) == ["a", "a", "b", "b", "c", "c"]


def test_summary_uses_equal_case_weight_and_absolute_throughput():
    cases = ["loads:a", "dumps:a"]
    runs = []
    for _ in range(2):
        runs.append({"libraries": {
            "ours": {case: {"timing": {"median_latency_ns": value}} for case, value in zip(cases, [100, 800])},
            "reference": {case: {"timing": {"median_latency_ns": value}} for case, value in zip(cases, [200, 200])},
        }})
    result = benchmark.summarize(runs, cases, {case: {"work_bytes": 1000} for case in cases}, ["reference"])
    assert result["cases"]["loads:a"]["measurements"]["ours"]["throughput_MB_s"] == 10000
    groups = result["geomeans"]["reference"]["ours"]
    assert groups["loads"]["latency_ratio"] == 0.5
    assert groups["dumps"]["latency_ratio"] == 4
    assert groups["combined"]["latency_ratio"] == pytest.approx(math.sqrt(2))
    assert groups["combined"]["case_count"] == 2
    assert groups["combined"]["faster_cases"] == 1


@pytest.mark.parametrize("enabled", [True, False])
def test_measure_restores_gc_state(monkeypatch, enabled):
    original = gc.isenabled()
    gc.enable() if enabled else gc.disable()
    monkeypatch.setattr(benchmark, "timed_calls", lambda function, argument, count: count * 100)
    try:
        result = benchmark.measure(lambda _: None, None, 0.001, 3, 0)
        assert result["sample_latency_ns"] == [100, 100, 100]
        assert gc.isenabled() == enabled
    finally:
        gc.enable() if original else gc.disable()


def make_library(tmp_path, name, version="test-version"):
    package = tmp_path / name
    package.mkdir()
    (package / "corpus_test_adapter.py").write_text(
        "import json\n"
        f"__version__ = {version!r}\n"
        "loads = json.loads\n"
        "def dumps(value):\n"
        "    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')\n"
    )
    return {
        "name": name, "module": "corpus_test_adapter", "python": sys.executable,
        "pythonpath": [str(package)], "expected_version": version,
    }


@pytest.mark.parametrize("field,value", [
    ("name", "../private-path"), ("module", "invalid-module"),
    ("expected_version", None), ("revision", "short"),
    ("wheel_sha256", "invalid"), ("pythonpath", "not-a-list"),
    ("pythonpath", ["missing-directory"]), ("unknown_field", "not-supported"),
])
def test_library_configuration_rejects_bad_fields(tmp_path, field, value):
    library = make_library(tmp_path, "fixture")
    library[field] = value
    path = tmp_path / "libraries.json"
    path.write_text(json.dumps({"libraries": [library]}))
    with pytest.raises(ValueError):
        benchmark.load_libraries(path)


def test_end_to_end_two_reference_versions_and_portable_results(tmp_path):
    raw = b'{"key":[1,1.5,true,null,"value"]}'
    (tmp_path / "small.json").write_bytes(raw)
    (tmp_path / "copy.json").write_bytes(raw)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest([document("small", raw), document("copy", raw)])))
    libraries = [make_library(tmp_path, name, version) for name, version in (
        ("ours", "test-version"), ("current", "3.12.0"), ("control", "3.11.9"),
    )]
    libraries_path = tmp_path / "libraries.json"
    libraries_path.write_text(json.dumps({"libraries": libraries}))
    output = tmp_path / "result.json"
    command = [
        sys.executable, benchmark.__file__, "run", "--manifest", str(manifest_path),
        "--directory", str(tmp_path), "--libraries", str(libraries_path),
        "--reference", "current", "--reference", "control", "--output", str(output),
        "--repeats", "2", "--samples", "1", "--seconds", "0.0001", "--warmups", "0",
    ]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    text = output.read_text()
    result = json.loads(text)
    assert str(tmp_path) not in text
    assert result["active_cases"] == ["loads:small", "dumps:small"]
    assert result["duplicate_cases"] == {"loads:copy": "loads:small", "dumps:copy": "dumps:small"}
    assert result["libraries"]["current"]["version"] == "3.12.0"
    assert result["libraries"]["control"]["version"] == "3.11.9"
    assert set(result["summary"]["geomeans"]) == {"current", "control"}
    assert len(result["runs"]) == 2
    assert set(result["verification"]) == {"ours", "current", "control"}
    for case in result["summary"]["cases"].values():
        assert all(value["latency_ns"] > 0 for value in case["measurements"].values())


def test_child_rejects_wrong_version_before_timing(tmp_path):
    library = make_library(tmp_path, "wrong-version")
    library["expected_version"] = "not-installed"
    with pytest.raises(ValueError, match="version.*expected"):
        benchmark.child(library, {"cpu": None}, 1729, 30)


def test_import_cannot_silently_use_another_build(tmp_path):
    library = {"name": "wrong-build", "module": "json", "expected_version": json.__version__, "pythonpath": [str(tmp_path)]}
    with pytest.raises(ValueError, match="not imported from"):
        benchmark.module_metadata(library, json)


def test_worker_rejects_build_drift(tmp_path):
    library = make_library(tmp_path, "build-drift")
    with pytest.raises(ValueError, match="changed after verification"):
        benchmark.child(library, {"cpu": None, "expected_metadata": {}}, 1729, 30)


def test_worker_rejects_changed_benchmark_code():
    with pytest.raises(ValueError, match="benchmark source changed"):
        benchmark.worker({"expected_sources": {}})


def test_preflight_rejects_byte_differences_before_any_timing(monkeypatch):
    calls = []

    def child(library, payload, hash_seed, timeout):
        calls.append(payload["mode"])
        return {"metadata": {}, "cases": {"dumps:a": {"output_sha256": library["name"]}}}

    monkeypatch.setattr(benchmark, "child", child)
    with pytest.raises(ValueError, match="output differs"):
        benchmark.verify_builds([{"name": "a"}, {"name": "b"}], {}, ["a"], 30)
    assert calls == ["verify", "verify"]
