# Match orjson behavior and remove unnecessary allocations

Status: completed (2026-08-26). This plan follows PLANS.md and the plans-md skill. It continues
the completed performance work in ../orjson-performance/plan.md. That work met
the original small/medium timing targets but did not establish drop-in behavior.

## Purpose / Big Picture

Make the complete-document Python frontend match orjson 3.11.9 for integer
overflow, nesting boundaries, Fragment, converted dictionary keys, float bytes,
input exceptions, NumPy, and supported Python objects/options. Preserve the
independent streaming fixes and avoid new allocation or native-stack hazards.
Measure allocations and timing rather than assuming compatibility costs speed.

## Plan Layout

This file tracks implementation and completion. record.md records oracle cases,
test results, allocation experiments, timings, and remaining discrepancies.
Raw profiles and upstream reference checkouts stay under /tmp. No private
project information or private datasets belong in any public artifact.

## Progress

- [x] Inspect b84ba61, the completed performance plan, and current implementation.
- [x] Pin orjson 3.11.9 behavior with differential regressions and upstream tests.
- [x] Match loads integer, nesting, and exception behavior.
- [x] Match Fragment, float output, dictionary-key, and object serialization.
- [x] Match supported NumPy dtypes, shape/layout rules, and float precision.
- [x] Confirm shallow-stack optimization: small dumps 1.80x, one fewer allocation; release unused output before Python callbacks.
- [x] (2026-08-26) Update documentation, publish to PR #1, and verify all 21 implementation checks on b145ac3.

## Surprises & Discoveries

The previous fallback copied the object graph into Python containers, serialized
with stdlib JSON, and replaced random Fragment placeholders. This allocated
unnecessarily and caused key-collision and float-format incompatibilities.
The native decoder already uses a heap stack, so matching orjson's larger decode
depth need not reintroduce native recursion. orjson's decode and encode limits
differ, and some mixed dataclass nesting wraps its recursion counter.

## Decision Log

Decision: Use the installed orjson 3.11.9 wheel and that release's public source
and tests as the behavioral oracle, including exact bytes and exception classes.
Rationale: Tests of ordinary JSON value equality missed public API differences.
Date: 2026-08-25.

Decision: Replace previous policy differences with orjson behavior when the user
explicitly requested parity. Keep malformed native exporter restrictions unless
an equally safe compatible implementation is established. Fragment is an
explicit raw-output API, not untrusted JSON parsing.
Rationale: Compatibility and security require an explicit input contract, not
undocumented changes to user-visible values or output.
Date: 2026-08-25.

Decision: Do not add optional duplicate rejection. Preserve duplicate output
keys and keep last-value-wins decoding. The isolated existing membership check
cost 2-10% in preprocessing, and a new serializer needs no tracking set.
Date: 2026-08-25.

Decision: Keep checked NumPy calendar arithmetic and bounded mixed dataclass
nesting instead of reproducing reference process faults and counter overflow.
Keep owning snapshots before callbacks. These restrictions are documented.
Date: 2026-08-25.

## Outcomes & Retrospective

The local suite passes 223 tests. The public release suite passes 1,626 tests,
including Faker and process-memory tests, with six skips and four package
identity assertions deselected. NumPy and ordinary small/medium workloads meet
2x in the recorded runs. Dataclasses and several other workloads remain slower.
Allocation profiling, timing confirmation, and implementation publication are
complete. All 21 CI checks pass on b145ac3, including Python 3.9/3.13, Miri,
fuzzing, flamegraph, and all six benchmark jobs. PR #1 remains ready for review.

The 15-round confirmation measures small loads/dumps at 1.24x/1.77x and medium
loads/dumps at 1.76x/1.88x. NumPy measures 1.11x-1.26x. The late-callback peak
falls 44%, and shallow native calls allocate once less. This is not universal
2x performance: dataclasses remain 21.20x, sorted dictionaries 2.36x, and integer
arrays 2.76x. Buffer-owner restrictions, callback snapshots, and checked handling
of reference overflow/fault cases remain documented compatibility restrictions.

## Context and Orientation

Work in /home/dev-user/code/jsonmodem on dev/friel/orjson-frontend. The public
fork is friel-openai/jsonmodem, PR #1, already ready for review. Do not revert it
to draft. Starting commit is b84ba61. Native loads/dumps are in
crates/jsonmodem-py/src/compat.rs; Python fallback and exports are in
crates/jsonmodem-py/python/jsonmodem/__init__.py. The token reader is
crates/jsonmodem/src/document.rs. Streaming APIs are separate in lib.rs.

## Plan of Work

First obtain public release tests and write a local differential harness that
compares output bytes, decoded types, and exception classes. Record boundaries
instead of inferring them from prose. Then correct native loads and replace
Fragment placeholders and dictionary preprocessing with direct output. Keep
callback execution outside native iterators or take owning snapshots before
callbacks. Implement uncommon object conversion explicitly, and handle NumPy
using checked access and native formatting rather than a blanket tolist().

Profile allocations for small/medium JSON, sorted keys, Fragment, callback,
dataclass, and NumPy workloads. Retain optimizations only when differential and
resource-limit tests pass. Update the benchmark record without hiding slower
workloads. Publish tested changes and monitor the existing PR.

## Concrete Steps

Run from /home/dev-user/code/jsonmodem, always activating its local environment:

    source .venv/bin/activate
    maturin develop --uv -m crates/jsonmodem-py/Cargo.toml --release
    python -m pytest -q crates/jsonmodem-py/tests
    python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py --seconds 0.1
    .agent/check.sh
    .agent/check-py.sh
    cargo clippy -p jsonmodem-py --all-targets -- -D warnings

## Validation and Acceptance

Every named discrepancy must have a failing-before/passing-after differential
test. Exercise supported public types/options against the release tests, exact
float bytes, integer boundaries, nesting, malformed input, cycles, and callback
mutation. Retain memory-limited streaming and small-stack native regressions.
Preserve the original small/medium <=2x timings and report other measurements.
Record allocation counts or peak memory with the profiler and its limitations.
Do not claim parity for any untested or unresolved behavior. Required CI must
pass on the final published commit before completing the goal.

## Idempotence and Recovery

Reuse the existing fork and branch. Keep temporary source checkouts and profiles
outside the repository. Never reset unrelated work. Commit validated changes;
normal builds and benchmarks are repeatable.

## Artifacts and Notes

The previous benchmark and security results are in ../orjson-performance/record.md.
They are a baseline, not evidence of compatibility for this plan.

## Interfaces and Dependencies

No runtime calls to orjson. It is a test/benchmark dependency only. NumPy support
must remain optional at import time. Use safe Rust/PyO3 and checked CPython APIs;
do not interpret unchecked third-party buffer metadata as trusted Rust slices.
Interpreter-specific wheels are packaging, not an API incompatibility; test the
supported interpreter range and document the build choice precisely.

Updated 2026-08-26: implementation CI passed all 21 checks. The completed plan
and record preserve measured limitations; the goal's last check is CI on the
documentation-only completion commit.
