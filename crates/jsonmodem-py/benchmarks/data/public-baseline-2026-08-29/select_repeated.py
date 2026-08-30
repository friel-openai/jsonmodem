"""Export the two reported libraries from one hash-pinned benchmark result."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import sys


SOURCE_SHA256 = "df9c917b8852d86f48aa17c197f16692c97673fe3e3e85be45a26343988fa644"
SUMMARY_HELPER_SHA256 = "b00c361b29535abfc16548de41a32a5d4caa0737e4989d80991c1d9041a9bbe9"
CORPUS_HELPER_SHA256 = "6a7ba7893d0e3ec83ef0cd70043eb29893eb2e8a7730476dcf02c0ec8cc9505c"
LIBRARIES = ("baseline", "orjson_3119")
REFERENCES = ("orjson_3119",)


def selected(mapping):
    return {name: value for name, value in mapping.items() if name in LIBRARIES}


def source_summary(source):
    expected = copy.deepcopy(source["summary"])
    for case in expected["cases"].values():
        case["measurements"] = selected(case["measurements"])
        case["ratios"] = {reference: selected(case["ratios"][reference]) for reference in REFERENCES}
    expected["geomeans"] = {
        reference: selected(expected["geomeans"][reference]) for reference in REFERENCES
    }
    return expected


def strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def check_samples(source, result):
    if len(source["runs"]) != 8 or len(result["runs"]) != 8:
        raise AssertionError("expected eight process repeats")
    if len(result["active_cases"]) != 36 or result["duplicate_cases"]:
        raise AssertionError("expected 36 unique document/operation cases")
    samples = 0
    for original, exported in zip(source["runs"], result["runs"], strict=True):
        if exported["libraries"] != selected(original["libraries"]):
            raise AssertionError("export changed a retained library's measurements")
        for name in LIBRARIES:
            if set(exported["libraries"][name]) != set(result["active_cases"]):
                raise AssertionError("export omitted or added a case")
            for record in exported["libraries"][name].values():
                timing = record["timing"]
                elapsed = timing["sample_elapsed_ns"]
                latencies = timing["sample_latency_ns"]
                iterations = timing["iterations_per_sample"]
                if len(elapsed) != 3 or len(latencies) != 3 or iterations < 1:
                    raise AssertionError("unexpected timing sample count")
                if any(value <= 0 for value in elapsed + latencies):
                    raise AssertionError("nonpositive elapsed time or latency")
                if latencies != [value / iterations for value in elapsed]:
                    raise AssertionError("per-call latency does not match elapsed time")
                if timing["median_latency_ns"] != statistics.median(latencies):
                    raise AssertionError("sample median does not match the retained samples")
                samples += len(latencies)
    if samples != 1728:
        raise AssertionError("expected 1,728 retained timing samples")
    return samples


def export(source, summarize):
    if len(source["libraries"]) != 4:
        raise AssertionError("expected four libraries in the source session")
    if any(name not in source["libraries"] for name in LIBRARIES):
        raise AssertionError("a selected library is absent")
    result = copy.deepcopy(source)
    result["libraries"] = selected(result["libraries"])
    result["verification"] = selected(result["verification"])
    result["references"] = list(REFERENCES)
    for run in result["runs"]:
        # Retain schedule positions because omitted builds ran between some workers.
        run["source_library_positions"] = {
            name: position for position, name in enumerate(run["library_order"], start=1)
            if name in LIBRARIES
        }
        run["library_order"] = [name for name in run["library_order"] if name in LIBRARIES]
        run["libraries"] = selected(run["libraries"])
    result["summary"] = summarize(
        result["runs"], result["active_cases"], result["verification"][LIBRARIES[0]],
        result["references"],
    )
    if result["summary"] != source_summary(source):
        raise AssertionError("recomputed selected summaries differ from the original")
    samples = check_samples(source, result)
    omitted = set(source["libraries"]) - set(LIBRARIES)
    if any(label in value for label in omitted for value in strings(result)):
        raise AssertionError("export still contains an omitted library label")
    result["publication_selection"] = {
        "source_result_sha256": SOURCE_SHA256,
        "source_library_count": 4,
        "selected_libraries": list(LIBRARIES),
        "selected_ratio_references": list(REFERENCES),
        "omitted_library_count": 2,
        "retained_libraries_have_discarded_samples": False,
        "retained_timing_samples": samples,
        "source_library_positions_are_one_based": True,
        "schedule_note": "This is a selection from a four-build session, not a new two-build run. Each run retains the selected libraries' positions in the original worker order.",
        "summary_note": "Summaries were recomputed from unchanged selected samples and checked against the original values.",
        "summary_helper_sha256": SUMMARY_HELPER_SHA256,
        "corpus_helper_sha256": CORPUS_HELPER_SHA256,
        "selection_generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        parser.error("source does not match the recorded original SHA-256")
    directory = Path(__file__).resolve().parents[2]
    for name, expected in (
        ("bench_public_corpus.py", SUMMARY_HELPER_SHA256),
        ("public_corpus.py", CORPUS_HELPER_SHA256),
    ):
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            parser.error(f"{name} differs from the recorded summary helper")
    sys.path.insert(0, str(directory))
    from bench_public_corpus import summarize

    source = json.loads(raw)
    result = export(source, summarize)
    # Exclusive creation prevents overwriting either an original or an earlier export.
    with args.output.open("x") as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write("\n")
    print("Retained 1,728 timing samples; checked all selected summaries against the original.")


if __name__ == "__main__":
    main()
