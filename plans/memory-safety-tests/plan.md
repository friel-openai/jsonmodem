# Test unsafe streaming code and Python buffers


Status: active on 2026-08-26. Implementation is underway. This plan follows
`PLANS.md` and uses `plan.md` and `record.md` as requested. Keep Progress,
Surprises and Discoveries, Decision Log, and Outcomes and Retrospective current.

## Purpose / Big Picture


Make the memory-safety checks for jsonmodem's streaming parser and Python binding
specific and reproducible. Today, a passing Miri job says little about the Python
binding because that crate is excluded. Some Rust integration tests are also
excluded, and the pointer traversal has no dedicated unit tests.

After this work, contributors will have tests tied to the assumptions behind
each relevant `unsafe` block, a Miri command for the Rust tests, and a native
memory-checking command for the Python extension. Confirmed defects will have
regression tests and fixes. Passing these checks will not be described as proof
that all possible inputs and Python objects are safe.

## Plan Layout


`plans/memory-safety-tests/plan.md` owns scope, decisions, and completion status.
`plans/memory-safety-tests/record.md` holds the safety assumptions, named tests,
commands, results, and remaining omissions. Follow the existing repository
convention of storing plans under `plans/<task>/`.

Keep only compact, public evidence in these files. Put build products, full logs,
generated corpora, and temporary fault-injection programs outside tracked files.
Before publication, summarize the record and review the diff. No merge is
authorized by this plan; this cleanup rule applies regardless of merge method.

## Work Boundaries


Use branch `dev/friel/memory-safety-tests` in the separate worktree created from
`upstream/main` at `47a542760f84dd402cecda6476b56dc92dae54e5`. Do not merge or
cherry-pick the orjson frontend PR to obtain these changes. The base repository
is `AaronFriel/jsonmodem`; the user's publishing fork is `friel-openai/jsonmodem`.

The primary files are `crates/jsonmodem/src/parser/scanner/mod.rs`, its
`tests.rs`, `crates/jsonmodem/src/backend/std/value_zipper.rs`, and
`crates/jsonmodem-py/src/lib.rs`. Related Rust integration tests, Python tests,
`.github/workflows/miri.yml`, `.config/nextest.toml`, and `.agent/` test scripts
are in scope. Follow callers into `parser/mod.rs` and `value_applicator.rs` when
needed to establish a safety assumption. Do not turn this into a repository-wide
rewrite or add runtime dependencies for test infrastructure.

Preserve streaming events, partial values, supported buffer inputs, and normal
performance. Start with tests and test-only assertions. Change production code
only for a demonstrated defect or a necessary clarification of an unsafe
operation's preconditions. Record and measure any runtime change.

PR #1 and its active `plans/orjson-security-audit/plan.md` remain separate. That
audit concerns the frontend and changes made by PR #1; this plan concerns
upstream streaming code and repeatable memory-safety testing. Do not edit that
checkout or its plans. If both efforts discover the same defect, coordinate
which branch owns the fix before publishing duplicate changes. Do not copy
private source, usage details, payloads, project information, or communications
into this repository. All test inputs must be synthetic or already public.

## Definition of Done


Each explicit unsafe operation in the three primary source files has a recorded
safety assumption, an explanation of how callers enforce it, and named tests
that exercise it. Any assumption that cannot be tested is listed as a limitation.
The record distinguishes source inspection, actual Miri execution, and native
sanitizer execution. It does not infer coverage from compilation or test totals.

Scanner tests check valid UTF-8 at every unchecked conversion in test builds.
Dedicated ValueZipper tests exercise allocation growth, sibling changes,
replacement, and root reuse. Relevant behavior currently hidden behind snapshot
test exclusions has plain assertions that run under Miri. The tests run with
both reference-aliasing models described below and recorded deterministic seeds.

Python buffer and object-lifetime tests run against an instrumented extension.
A temporary known-bad program confirms that the native memory checker is active.
The record states whether CPython itself is instrumented and what remains
outside detection. There must be no unexplained memory-checking reports.

Existing Rust and Python tests still pass. Every confirmed production defect has
a minimal reproducer that fails before its fix and passes after. A separate PR,
when publication is requested, must contain no dependency on PR #1 and have all
required checks green before it is marked ready. Do not merge either PR.

## Progress


- [x] (2026-08-26 05:26Z) Inspect upstream, the Miri workflow, test exclusions, and buffer handling.
- [x] (2026-08-26 05:26Z) Create an independent worktree and branch at upstream `47a5427`.
- [x] (2026-08-26 05:26Z) Write this plan and the initial evidence record.
- [x] (2026-08-26) Map each unsafe operation to its safety assumptions and named tests; document untested cases.
- [x] (2026-08-26) Add six scanner/ValueZipper unit tests and four integration tests. No production defect reproduced so far.
- [ ] Finish all six targeted Miri configurations and the full suite (completed: default model seeds 0 and 1; remaining: other seeds/model and full-suite completion).
- [x] (2026-08-26) Verify native instrumentation with a required failure check; pass 50 Python tests on CPython 3.12.
- [x] (2026-08-26) Add CI commands, local scripts, prerequisites, and coverage documentation.
- [ ] Run final checks, review the independent diff, and summarize results.

## Surprises and Discoveries


The upstream Miri workflow already excludes `jsonmodem-py` and
`jsonmodem-fuzz`. The exclusions do not depend on PR #1. ValueZipper is unchanged
between upstream and PR #1. The scanner has a numeric accumulation fix in PR #1,
but its unchecked UTF-8 conversions and existing tests are already upstream.

The repository's `.agent/check.sh` compiles a Clippy configuration with
`cfg(miri)`, but skips actual Miri execution by default. The optional Miri command
also differs from the workflow's crate exclusions. Neither compilation nor a
skipped command is execution evidence.

## Decision Log


2026-08-26, Codex: Base the work on upstream `47a5427`, not PR #1. All three
reviewed areas exist upstream, so adding safety tests does not require the
orjson-compatible API. This permits independent review and merging.

2026-08-26, Codex: Keep one plan with separate Rust and Python milestones.
Miri interprets Rust operations; the existing CPython calls need a separate
native test arrangement. Removing the Python exclusion without addressing those
calls would not establish coverage.

2026-08-26, Codex: Prepare the plan and worktree now. Implementation and
publication remain unchecked; no source edits or new PR are part of this setup.

## Outcomes and Retrospective


The independent worktree now contains deterministic Rust tests, Python buffer
and lifetime tests, Miri and AddressSanitizer scripts, and CI jobs. Native
instrumentation has been verified by a deliberate failure, and 50 Python tests
pass on CPython 3.12. Final Miri validation and review are still running. The
existing PR and its uncommitted audit work were left untouched.

## Context and Orientation


Miri executes Rust tests while checking for certain invalid memory operations.
It can detect a dangling pointer in a test that uses that pointer, but a green
job does not prove every possible use is valid. Its Stacked Borrows and Tree
Borrows models check rules governing overlapping references. Test both without
disabling their checks; record the Rust nightly version because these tools
change over time.

The scanner builds strings from input batches and saved fragments. Four
`from_utf8_unchecked` calls assume that the selected bytes form valid UTF-8.
`ValueZipper` stores raw pointers to values inside a boxed root, vectors, and
ordered maps. Pointers must remain valid when those containers grow or change.
Its current traversal expects parser depth changes of one level at a time.

The Python binding obtains buffer pointers with `PyObject_GetBuffer`, constructs
Rust slices, and releases the buffer through `PyBufferGuard`. Other unsafe
operations handle Python object references. Correctness depends on pointer
validity, lengths, ownership, and object lifetimes. A native extension that lies
about the allocation behind a pointer is a separate trust assumption; checking
metadata alone cannot prove that arbitrary native memory exists.

AddressSanitizer adds runtime checks to native code for errors such as reads
beyond allocated memory and use after free. It complements Miri but does not
check all Rust reference rules. An ordinary Python test run is neither test.

## Plan of Work


### 1. Record assumptions and establish the baseline


For every unsafe expression in the three primary files, record its function,
operation, required assumptions, enforcing caller, and existing tests in
`record.md`. Trace Python reference ownership and every buffer release on both
success and error. Inspect parser call sequences before designing direct zipper
tests; do not accidentally treat an impossible internal sequence as normal use.
If a safe callable API permits such a sequence, determine whether it must reject
it rather than relying on a debug-only assertion.

Run the existing focused scanner tests, core checks, and Python tests. List which
tests Miri actually executes. Record excluded crates and compiled-out tests
separately from ignored tests. Preserve any baseline failure with its input and
command before changing code.

### 2. Exercise string construction and pointer lifetimes


Extend `crates/jsonmodem/src/parser/scanner/tests.rs` with deterministic tests
covering empty strings, ASCII, two- through four-byte Unicode characters,
escapes, carried fragments, and borrowed-to-owned transitions. Exercise each
unchecked conversion. In test or Miri builds, validate its input with
`str::from_utf8` before the unchecked call, so a bad UTF-8 assumption fails
explicitly. Test malformed bytes through APIs that accept bytes; Rust `&str`
inputs must already be valid UTF-8. Do not create invalid Rust strings in tests.

Add a private test module in `value_zipper.rs`. Force vector capacity growth and
enough ordered-map insertions to exercise node growth. Follow valid parser
sequences through descent, ascent, siblings, repeated keys, replacing a value,
`with_leaf_mut`, `with_leaf`, and `take_root` followed by reuse. Assert complete
values and paths, not just absence of a crash. Add parser-level tests for the
same transitions so the direct tests do not stand alone.

For a memory error, save a small failing test before fixing production code.
Prefer removing an unnecessary unsafe operation or correcting pointer lifetime
over a new general-purpose abstraction. Keep tests that detect invalid UTF-8 and
pointer use out of release hot loops unless a runtime check is actually needed.

### 3. Make Rust coverage reproducible under Miri


Add `crates/jsonmodem/tests/memory_safety.rs` for deterministic streaming
integration assertions. Share plain assertion helpers with the existing values
and buffers tests where practical. Keep snapshot rendering separate so filesystem
access by `insta` does not exclude the underlying behavior from Miri.

Use a compact generated corpus with recorded seeds and exhaustive valid split
positions for short inputs. Include values and buffers adapters, repeated roots,
partial strings, early iterator drop, and parser error cleanup. Any byte split
that the API intentionally rejects must assert that rejection rather than
assuming arbitrary partial UTF-8 is accepted.

Run targeted tests with Miri seeds 0, 1, and 2 under both Stacked Borrows and Tree
Borrows. Retain the existing full Miri suite. Measure duration before setting CI
timeouts. Provide an explicit configurable case count for generated tests, with
the selected count printed in logs and passed into Miri's isolated environment.
Do not silently reduce the new safety tests to ten cases or confuse Miri's
execution seed with the generated-input seed.

### 4. Check the Python extension as native code


Add `crates/jsonmodem-py/tests/test_buffer_safety.py`. Exercise bytes, bytearray,
read-only and writable memoryviews, empty buffers, slices, unsupported layouts,
released views, invalid UTF-8, failed acquisition, and cleanup after exceptions.
Hold events and payload views after discarding the input or parser. Test partial
iterator consumption, repeated creation and destruction, and input mutation
where the documented API permits it. Verify the intended ownership or rejection
for each case.

Add `.agent/check-py-memory.sh` using a separate virtual environment and Cargo
target directory. First demonstrate a Linux AddressSanitizer build of the Rust
extension with a matching native runtime. Verify activation using a temporary
known-bad allocation test that must fail in a subprocess; never ship that code
as part of the production extension. Then run the targeted and existing Python
tests. Record compiler/runtime versions and whether CPython is instrumented.

Use subprocesses with timeouts for tests that could terminate the interpreter.
Exercise metadata rejection without dereferencing fabricated addresses. Do not
claim support for malicious native exporters or change the accepted buffer types
just to obtain a green job. If instrumentation cannot cover a required operation,
record the exact limitation and resolve the test approach before marking this
milestone complete. Any runtime fix must have its own before-and-after test.

### 5. Put the checks in CI and document the result


Update `.github/workflows/miri.yml` to execute the targeted tests in both models
with the selected seeds, while retaining the broader suite. Make local Miri
execution use consistent crate exclusions. Add
`.github/workflows/python-memory.yml` to call the proven native test script.
Document prerequisites in `.agent/setup.sh` or `.agent/setup-py.sh` and `AGENTS.md`
where needed. Do not add a job that passes after silently skipping instrumentation.

Document commands, covered assumptions, and remaining limitations in
`docs/memory-safety-testing.md`. Record the final test names and results in
`record.md`. Review the diff against the recorded upstream base. If source
changes affect streaming performance, compare the existing streaming benchmark
before and after on the same machine and record timings and allocation changes.
Do not use one-shot orjson throughput as this branch's performance target.

## Concrete Steps


Run commands from the new jsonmodem worktree. Initial checks use existing files:

    cargo test -p jsonmodem --lib parser::scanner::tests
    .agent/check.sh
    .agent/setup-py.sh
    .agent/check-py.sh
    cargo +nightly miri setup
    cargo +nightly miri nextest run --workspace --profile default-miri --exclude jsonmodem-fuzz --exclude jsonmodem-py

After adding the tests, the fastest checks are:

    cargo test -p jsonmodem --lib value_zipper
    cargo test -p jsonmodem --test memory_safety
    cargo +nightly miri test -p jsonmodem --lib value_zipper
    MIRIFLAGS="-Zmiri-tree-borrows -Zmiri-seed=0" cargo +nightly miri test -p jsonmodem --test memory_safety

Repeat targeted Miri commands for both models and all three selected seeds. The
default model uses `-Zmiri-seed=0` without `-Zmiri-tree-borrows`. For any configurable
test count, use `-Zmiri-env-set=NAME=VALUE` with the actual name added by the tests.
Write the final full commands in the record; this placeholder is not evidence.

After adding and verifying the native script, run:

    .agent/check-py-memory.sh

No sanitizer build recipe is claimed to work yet. Milestone 4 must establish and
record the exact build command, runtime loading, interpreter, and failure check.

## Validation and Acceptance


Fast checks are the focused tests above. Final validation includes
`.agent/check.sh`, `.agent/check-py.sh`, the full existing Miri suite, the new
targeted Miri runs, and the Python native memory checks. Add a release-mode run of
the Rust safety tests so debug assertions do not conceal reliance on missing
runtime validation. All must exit successfully with no unexplained diagnostic.

For a coverage-only test, demonstrate that it executes its intended operation
and asserts the relevant result. For a production bug, demonstrate a failing
baseline and passing fix. Where practical, temporarily inject a narrowly scoped
fault to show the new check catches it, then remove that fault and record the
result. Do not put deliberate undefined behavior in the normal test suite.

Final review checks every unsafe assumption against its named test and clearly
lists untested cases. A reviewer must be able to reproduce each result from the
recorded commit and commands. More passing tests alone do not meet acceptance.

## Idempotence and Recovery


Use this worktree's own Python environment and target directory. Do not rebuild
into PR #1's environment or reset its checkout. Keep fault injection and crash
artifacts in disposable locations. Repeat a failed command only after recording
whether the failure came from the test, setup, or unsupported instrumentation.
Do not suppress a memory error, disable reference checks, or increase a timeout
without recording why. Do not force-push or modify someone else's branch.

## Artifacts and Notes


`record.md` starts with baseline facts and then records each test attempt before
it runs: question, assumptions, input, method, expected evidence, and decision
rule. Afterward add the commit, exact command, tool versions, result, limitation,
and next action. Keep full transcripts outside Git and retain compact summaries.

## Interfaces and Dependencies


Keep the public Rust and Python interfaces unchanged unless a reproduced defect
requires a documented correction. Use existing Rust tests, `pytest`, PyO3,
Miri, and the native compiler's AddressSanitizer. Additional tools belong only in
development or CI setup. Do not add another parsing backend or depend on the
orjson frontend from PR #1.

## Next Action


Finish the remaining Miri runs, check the Python sanitizer script on CPython
3.13 to match CI, resolve concrete review findings, and record final validation.

Created 2026-08-26 to address missing memory-safety test coverage independently
of the orjson frontend PR.
