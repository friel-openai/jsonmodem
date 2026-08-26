# Measure additional complete-document speedups

Status: active. Follow PLANS.md and the plans-md skill. This plan continues the
completed orjson-compatibility plan without reopening its API decisions.

## Purpose / Big Picture

Make jsonmodem faster than orjson on additional, reproducible synthetic workloads.
Keep jsonmodem's streaming APIs, borrowed tokens, bounded stacks, and separate
complete-document frontend. Preserve grammar, ownership, numeric, and callback
checks. Do not add an orjson runtime dependency or publish private information.

## Progress

- [x] (2026-08-26) Inspect clean baseline 6bb32dd, benchmarks, and native writers.
- [x] Measure a fresh baseline and identify repeated work in native serialization.
- [x] Implement typed NumPy row loops and long-string capacity reservation; 281 binding tests pass.
- [x] Repeat timings, check allocations, and preserve streaming behavior.
- [ ] Publish the existing PR and verify final CI.

## Context and Orientation

Work in /home/dev-user/code/jsonmodem on dev/friel/orjson-frontend. Existing PR #1
in friel-openai/jsonmodem is ready for review. Baseline 6bb32dd has all 21 CI
checks passing. Complete-document loads/dumps live in crates/jsonmodem-py/src/compat.rs;
NumPy snapshot formatting lives in crates/jsonmodem-py/src/numpy.rs. The optional
Python adapters are in crates/jsonmodem-py/python/jsonmodem. Streaming code is
independent. No streaming API redesign is needed for this work.

The previous measurements place NumPy at 1.11x-1.26x orjson time and long-string
loads at 0.47x. The objective is additional measured wins, not relabeling an
existing win. The original small/medium <=2x results must remain true. Dataclasses
and other slower workloads must remain reported, not removed from comparisons.

## Plan of Work

First repeat the existing complete-document and object benchmarks against the
pinned orjson 3.11.9 wheel. Record hypotheses before editing. NumPy formatting
currently dispatches dtype and updates its dimension stack per scalar. Test
dispatch once per snapshot and a bounded loop over the innermost dimension.
Keep immutable bytes and checked dimension products. Also inspect output growth
and escaping before choosing any second change.

Use existing helpers rather than a second serializer. Add differential cases
for changed loops, including empty axes, shapes, indentation, non-finite numbers,
and malformed snapshot metadata. Run complete-document and streaming tests.
Retain changes only with repeatable timing improvement and no compatibility or
security regression. Publish measurements that include unchanged and slower cases.

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

Require exact output equality before timing. Use CPU-pinned alternating batches,
at least eleven rounds, and a separate confirmation run. Report paired median
jsonmodem/orjson ratios and raw sample locations. Seek at least two additional
representative cases below 1.0 in both runs; prefer a margin of ten percent.
Keep every original benchmark and report regressions rather than selecting only
favorable inputs. Measure Memray independently of timing, compared with orjson.
All existing tests and final-commit CI must pass before completion.

## Surprises & Discoveries

The Python adapter already returns a top-level NumPy result directly. There is
no extra Python bytearray copy to remove there. Repeated native element dispatch
and dimension bookkeeping are the first hypothesis instead.

Exploratory NumPy ratios improve from 1.27x/1.18x/1.11x to
0.68x/0.87x/0.86x for existing int64/float32/float64 arrays. Flat and wide arrays
remain slower. Reserving for every string regresses small writes, so the final
candidate reserves only strings at least 256 bytes long.

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

Keep loads/dumps, streaming methods, and NumPy optional-import behavior unchanged.
Do not weaken native-exporter restrictions or replace checked snapshot reads
with borrowed foreign pointers. Retain iterative depth handling and callbacks
only after releasing native container iterators.

## Outcomes & Retrospective

Two independent full runs confirm NumPy int64, float32, and float64 at
0.69x, 0.86x, and 0.86x orjson time on the existing 25,000x4 arrays. All fifteen
paired confirmation samples beat orjson in each case. Flat and wider-row controls
remain slower and are included in record.md. No streaming implementation,
public API, unsafe code, or dependency changes were required.

The long-string reservation removes one allocation per call and reduces peak
tracked bytes 33.3%, without a consistent below-2x timing result. Original
small/medium limits are preserved in both full and confirmation runs. Local
validation passes 281 binding tests and 1,626 public release tests, plus core
checks. Publication and final CI remain in progress.

Created 2026-08-26 to record and validate the requested additional speed pass.
