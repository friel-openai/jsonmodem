# Make the document frontend competitive with orjson

This living plan follows PLANS.md and the plans-md skill. Keep Progress, Surprises & Discoveries,
Decision Log, and Outcomes & Retrospective current.

## Purpose / Big Picture

Make jsonmodem.loads and jsonmodem.dumps take no more than twice the time of
orjson on the small object and 1,000-record document in
crates/jsonmodem-py/benchmarks/bench_orjson_compat.py. Also measure additional
synthetic workloads rather than optimizing only those two documents. This work
concerns the complete-document frontend, not the existing incremental API.

Strict grammar, Unicode checks, exact integers, bounded nesting, and callback
semantics remain required. Implement checks during parsing or serialization
instead of traversing the data repeatedly. Do not claim universal performance
or complete compatibility based on a small benchmark.

## Plan Layout

This file is the source of truth. record.md holds compact experiment intent,
starting commits, commands, measurements, security assumptions, and untested
conditions. Generated timing samples live under /tmp during development; only
compact reproducible results belong in the public repository. The existing
repository convention keeps plans under plans/. No additional tracker is used.

## Progress

- [x] (2026-08-25) Read the implementation, repository instructions, and benchmark.
- [x] (2026-08-25) Profile dumps: Python _prepare accounts for 0.585 of 0.666
  seconds for 100 medium-document serializations under cProfile.
- [x] Record alternating, CPU-pinned release-build baseline measurements.
- [x] Replace repeated parsing with strict single-pass document parsing.
- [x] Replace Python preprocessing for common types with native serialization.
- [x] Bound streaming depth before path/event allocation, including iterable feeds.
- [x] Preserve exact integer types and reject non-finite numbers in streaming APIs.
- [x] Fix finish() at numeric EOF and number capture across chunk boundaries.
- [x] Restrict borrowed buffers to built-in immutable owners; snapshot mutable inputs.
- [x] Add subprocess resource-limit tests and Python-binding fuzz/property coverage.
- [x] Run differential, adversarial, and mutation/callback regression tests.
- [x] Meet the two original workload targets; document other workloads.
- [ ] Update documentation, publish, and verify required CI.

## Surprises & Discoveries

The existing loads implementation traverses input to count nesting, asks
serde_json to validate grammar, copies and appends a delimiter, and parses
again with streaming events. It imports builtins and calls int or float for
each number. The existing dumps copies the entire object graph in Python and
then calls the standard-library encoder. These costs are architectural rather
than an unavoidable cost of validation.

The streaming binding also eagerly creates all events before returning from
feed. Deeply nested inputs clone paths of increasing length, producing
quadratic allocation without a parser depth bound. Its numeric backend uses
f64, finish does not finalize root numbers, and buffer handling trusts
arbitrary native exporters. These defects must be addressed in the streaming
APIs as well as the complete-document frontend. Miri only covers the core;
binding-specific subprocess and property tests are required evidence.

The binding currently targets abi3-py39. PyO3's string conversion must allocate
an encoded copy under that ABI because PyUnicode_AsUTF8AndSize entered the
stable ABI in Python 3.10. Per-interpreter wheels can use that public CPython
API on every supported Python version without private object-layout reads.

## Decision Log

Decision: The complete-document API must not call feed(), collect events, or
clone paths. Direct construction obviates eager event/path amplification and
incremental EOF handling for loads, but does not fix numeric conversion or
buffer ownership. Streaming APIs remain exposed and require separate fixes,
without making their architecture a dependency of frontend optimization.
Rationale: The replacement API receives the full document at entry. Its threat
model must follow the code it actually invokes, not all code in the package.
Date: 2026-08-25.

Decision: Keep the incremental parser API unchanged and add a complete-document
parser that emits borrowed tokens and validates grammar as it advances.
Rationale: Complete documents do not need incremental string fragments, path
objects, or delimiter padding. Integrating validation avoids a second parser.
Date: 2026-08-25.

Decision: Use heap-backed container stacks for native loads and dumps, and share
streaming path keys using Arc<str>.
Rationale: Review reproduced a decoder crash on a 64 KiB Python thread stack and
memory exhaustion from a 60 KiB document with one long key and many array events.
A depth bound alone did not prevent either case. The fixes remove native
recursion and repeated key-text allocation, respectively.
Date: 2026-08-25.

Decision: Implement common-type serialization in Rust using checked PyO3 APIs
and a growable byte buffer, preserving Python handling for uncommon types while
it remains compatible. Never forward to orjson at runtime.
Rationale: Profiling identifies Python per-value calls as the dominant cost.
Date: 2026-08-25.

## Outcomes & Retrospective

In progress. The third native benchmark meets the original small/medium targets:
loads 1.03x/1.73x and dumps 1.52x/1.83x. Integer-array serialization remains 3.00x;
escaped-string loads/dumps remain 2.04x/2.21x. Broader validation and publication
are unfinished. Depth, numeric integrity, and EOF binding regressions now pass.

## Context and Orientation

The checkout is /home/dev-user/code/jsonmodem, branch
dev/friel/orjson-frontend, published as friel-openai/jsonmodem PR #1. The core
crate lives in crates/jsonmodem. The binding is crates/jsonmodem-py/src/lib.rs;
the Python package is crates/jsonmodem-py/python/jsonmodem. The benchmark and
test_orjson_compat.py are in that binding crate. The existing PR is ready for
review and must not be returned to draft. All public changes must stand alone
without private project information or private test material.

## Plan of Work

First make the benchmark alternate libraries, calibrate iteration counts,
report versions and samples, and check results before measuring. Save baseline
JSON under /tmp. Profile representative inputs rather than whole test suites.

Next implement a strict complete-document token iterator in the core. Tokens
borrow their text from validated input and include punctuation, strings, and
number lexemes. String escapes allocate only when needed. Maintain grammar
state and depth during iteration. Construct Python containers directly from
tokens without a Rust value tree. Parse common integers and floats in Rust;
use Python's arbitrary-precision constructor only for integers outside 64 bits.

Then add native serialization for JSON's ordinary types. Write output directly,
check integers and nesting during traversal, preserve subclass passthrough,
and do not call user callbacks while holding a Rust iterator into a dictionary.
Keep unsupported-type fallback explicit. Test strict-integer boundaries,
Unicode, duplicate keys, fragments, and mutation during default callbacks.

## Concrete Steps

Run commands from /home/dev-user/code/jsonmodem. Build using the local virtual
environment explicitly so maturin cannot modify another project's environment:

    source .venv/bin/activate
    maturin develop --uv -m crates/jsonmodem-py/Cargo.toml --release
    .venv/bin/python -m pytest -q crates/jsonmodem-py/tests
    .venv/bin/python crates/jsonmodem-py/benchmarks/bench_orjson_compat.py
    .agent/check.sh
    .agent/check-py.sh
    cargo clippy -p jsonmodem-py --all-targets -- -D warnings

## Validation and Acceptance

Expect all existing tests to pass and new regressions to cover changed parsing
and serialization behavior. Compare randomized outputs with orjson for the
shared contract and with explicit expectations for documented differences.
Malformed inputs must raise Python exceptions, not abort or panic. Benchmark
both libraries in the same process with alternating order and CPU affinity.
The primary acceptance test is median paired time ratios at most 2.0 for
both operations on small and medium. Report each additional workload without
averaging away regressions. Do not weaken validation to pass this target.

## Idempotence and Recovery

Use the existing checkout and branch. Keep generated artifacts under ignored
directories or /tmp. Commit tested checkpoints; never reset unrelated changes.
The Python reference serializer can remain as a fallback until native support
is verified. All build and benchmark commands can be repeated.

## Artifacts and Notes

The previous benchmark used sequential library timings, two inputs, no CPU
pinning, and no saved samples. Its ratios identify a problem but are not a
sufficient benchmark methodology for the new performance claim.

## Interfaces and Dependencies

Use jsonmodem's Rust core for complete-document decoding and PyO3 for Python
ownership. Use safe Rust formatting and escaping. No runtime orjson dependency
is allowed. Development comparison uses orjson 3.11.9. Any wheel ABI changes
must be documented while retaining the declared Python support range.

Revision 2026-08-25: Created the plan after profiling showed redundant passes
and Python object preprocessing dominate the original frontend.

Revision 2026-08-25: Renamed to plan.md per plans-md and separated complete-
document architecture from streaming defects. Binding regression tests reproduce
13 failures, including process aborts under a 256 MiB address-space limit.
