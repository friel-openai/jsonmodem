# Measure additional complete-document speedups

Status: completed (2026-08-26). This plan follows PLANS.md and the plans-md skill.
It builds on the completed orjson-compatibility plan and keeps the same API behavior.

## Purpose / Big Picture

Make `loads()` or `dumps()` faster than orjson on more test inputs. Keep the
streaming APIs unchanged and continue reusing input text where it is safe to
do so. Keep nesting limits and the checks for invalid JSON, invalid memory,
number errors, and user callbacks. Do not call orjson from the implementation
or publish private information.

## Progress

- [x] (2026-08-26) Inspect clean baseline 6bb32dd, benchmarks, and native writers.
- [x] Measure a fresh baseline and identify repeated work in native serialization.
- [x] Choose the NumPy formatter once per array and reserve output space for long strings; 281 binding tests pass.
- [x] Repeat timings, check allocations, and preserve streaming behavior.
- [x] (2026-08-26) Publish implementation 4516f73 to PR #1; all 21 checks pass.

## Context and Orientation

Work in /home/dev-user/code/jsonmodem on dev/friel/orjson-frontend. Existing PR #1
in friel-openai/jsonmodem is ready for review. Baseline 6bb32dd has all 21 CI
checks passing. Complete-document loads/dumps live in crates/jsonmodem-py/src/compat.rs;
NumPy formatting lives in crates/jsonmodem-py/src/numpy.rs. It reads an immutable
copy of each array's bytes. The optional
Python adapters are in crates/jsonmodem-py/python/jsonmodem. Streaming code is
independent. No streaming API redesign is needed for this work.

The earlier NumPy tests took 1.11 to 1.26 times as long as orjson. Long-string
loads took 0.47 times as long, so that was already a faster case. This plan
required additional improvements. Small and medium documents must still take
no more than twice orjson's time. Dataclasses
and other slower workloads must remain reported, not removed from comparisons.

## Plan of Work

First repeat the existing benchmarks against orjson 3.11.9. Record what each
proposed change should improve before editing. The starting NumPy writer checked
the number type and updated its position in the outer array for every element.
Test choosing the formatter once per array and processing each row together.
Continue reading an immutable byte copy and checking array-size arithmetic.
Also inspect output-buffer growth and string escaping before choosing a second change.

Use the existing writer. Add tests that compare its bytes with orjson, including
empty dimensions, different array layouts, indentation, NaN, and infinity.
Also test incorrect array sizes and byte lengths. Run complete-document and
streaming tests. Keep a change only if its improvement repeats and it preserves
compatibility and security checks. Report unchanged and slower cases too.

## Concrete Steps

From the public checkout:

    source .venv/bin/activate
    maturin develop --uv -m crates/jsonmodem-py/Cargo.toml --release
    python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py --seconds 0.1 --output /tmp/jsonmodem-speedups-base.json
    python crates/jsonmodem-py/benchmarks/bench_compat_objects.py --seconds 0.1 --output /tmp/jsonmodem-speedups-objects-base.json
    python -m pytest -q crates/jsonmodem-py/tests
    python crates/jsonmodem-py/benchmarks/check_orjson_release.py /tmp/jsonmodem-orjson-reference
    .agent/check.sh
    cargo clippy -p jsonmodem-py --all-targets -- -D warnings

Use distinct artifact names for subsequent experiments. The reference checkout
remains external and retains its public tests and license. Process-memory tests
may need approved escalation because sandbox PID visibility differs.

## Validation and Acceptance

Check exact output bytes before timing. Use one CPU core and take at least
11 measurements per library, alternating which runs first. Each measurement
must time many calls on the same input, then divide elapsed time by call count.
For each pair, divide jsonmodem's time per call by orjson's and report the
median, or middle, ratio. Repeat the experiment separately and keep all raw data.
Require at least two additional inputs below 1.0 in both experiments; prefer
at least ten percent less time than orjson.
Keep every original benchmark and report regressions rather than selecting only
favorable inputs. Measure Memray independently of timing, compared with orjson.
All existing tests and final-commit CI must pass before completion.

## Surprises & Discoveries

The Python adapter already returns a top-level NumPy result directly. There is
no extra Python bytearray copy to remove there. Repeated number-type checks
and array-position updates were the first operations investigated instead.

Exploratory NumPy ratios improve from 1.27x/1.18x/1.11x to
0.68x/0.87x/0.86x for existing int64/float32/float64 arrays. Flat and wide arrays
remain slower. Reserving output space for every string slowed small writes,
so the final code reserves it only for strings at least 256 bytes long.

## Decision Log

2026-08-26: Use a new public plan for another measured optimization pass. Keep
the previous compatibility decisions and memory results intact. Use synthetic
public benchmarks only; no internal feature inventory belongs here.

## Idempotence and Recovery

Reuse the existing branch and ready PR. Revert only this pass's experiments with
explicit patches if unsuccessful; do not reset unrelated work. Build and test
commands are repeatable. No new public API or dependency is planned.

## Artifacts and Notes

record.md records preregistered experiments, commands, measurements, rejected
changes, test results, and publication. Temporary raw profiles stay under /tmp.

## Interfaces and Dependencies

Keep loads/dumps and streaming methods unchanged. NumPy must remain optional.
Do not accept additional native buffer owners or replace checked reads of copied
bytes with reads from arbitrary native pointers. Continue tracking nesting
without recursive Rust calls, and release Rust container iterators before
calling user code.

## Outcomes & Retrospective

Two separate experiments found that writing the tested NumPy arrays took
31% less time than orjson for int64, and 14% less for float32 and float64.
Each array contained 100,000 numbers in 25,000 rows of four. jsonmodem beat
orjson in every one of the repeat experiment's 15 comparisons for each type.
One-dimensional arrays and arrays with 100 elements per row remained slower;
record.md includes those results. Streaming code and public APIs are unchanged.
No new unsafe code or dependency was added.

Reserving output space for long strings removes one allocation per call and
reduces the most memory held at once, as tracked by Memray, by 33.3%.
Long-string serialization still sometimes takes more than twice as long as orjson.
Small and medium documents stay below twice orjson's time in both experiments. Local
validation passes 281 binding tests and 1,626 public release tests, plus core
checks. All 21 CI checks pass on implementation 4516f73, including Miri,
Python 3.9/3.13, fuzzing, flamegraph, and all six benchmark jobs. PR #1 remains
ready for review. Documentation commit `456eec5` also passed all 21 checks.

Created 2026-08-26 to record and validate the requested additional speed pass.
Updated 2026-08-26 after implementation CI passed, preserving both the measured
wins and the slower cases. The results do not establish a speed advantage on all inputs.
