# Test unsafe streaming code and Python buffers


Status: implementation complete; upstream publication in progress (2026-08-26).
This plan follows `PLANS.md`. Keep Progress, Decision Log, and Outcomes current
until the upstream PR's final checks pass.

## Purpose / Big Picture


Make memory-safety testing reproducible for jsonmodem's streaming scanner,
raw-pointer value traversal, and Python buffer handling. The previous Miri job
excluded the Python crate and some Rust integration tests. The new tests found
two Python input ownership defects, which this branch fixes.

## Plan Layout


This file owns scope and completion status. `record.md` records regressions,
commands, measurements, and publication evidence. `docs/memory-safety-testing.md`
maps unsafe operations to tests and explains the tools' limits. Full logs,
wheels, and generated measurement data remain outside tracked files. Planning
notes were condensed before publication; their earlier versions remain in Git.

## Work Boundaries


Branch `dev/friel/memory-safety-tests` starts directly at upstream
`47a542760f84dd402cecda6476b56dc92dae54e5`. It does not depend on the separate
orjson frontend work. Publish from `friel-openai/jsonmodem` to
`AaronFriel/jsonmodem:main`; do not merge or modify another PR.

Changes cover `crates/jsonmodem/src/parser/scanner/`,
`crates/jsonmodem/src/backend/std/value_zipper.rs`, Python buffer handling in
`crates/jsonmodem-py/src/lib.rs`, their tests, and test tooling. Use only public
or synthetic inputs. Preserve streaming events, supported valid inputs, and
borrowing of known immutable storage. Do not add runtime dependencies.

## Definition of Done


Each explicit unsafe operation in the three source areas has a recorded safety
assumption and named tests, or an explicit limitation. Relevant Rust tests run
under Miri, including targeted runs under both reference models with three
execution seeds. Python tests run with verified native instrumentation. Every
confirmed defect has a failing baseline and a passing regression after the fix.

Existing tests pass. Performance and allocation changes are measured. The
separate upstream PR is labeled `jsonmodem` if repository permissions allow it,
and becomes ready for review after required checks pass on its final head.
Document any permission limitation rather than bypassing repository controls.
No merge is authorized.

## Progress


- [x] (2026-08-26) Create the independent worktree from upstream `47a5427`.
- [x] (2026-08-26) Record unsafe assumptions and add six unit tests and four integration tests.
- [x] (2026-08-26) Pass 188 full-suite Miri tests and six targeted configurations.
- [x] (2026-08-26) Reproduce and fix exporter reacquisition and Python 3.9 GC mutation of borrowed input.
- [x] (2026-08-26) Verify native instrumentation; pass 47 Python 3.9 tests and 52 Python 3.13 tests.
- [x] (2026-08-26) Measure streaming time and allocations; remove per-chunk attribute-name allocations.
- [x] (2026-08-26) Complete local checks and independent source review.
- [x] (2026-08-26) Refresh upstream once; confirm the base remains `47a5427` and no matching PR exists.
- [ ] Push the branch and create the upstream draft PR.
- [ ] Apply the project label, or record the upstream permission limitation.
- [ ] Verify final hosted checks and mark the PR ready.

## Surprises and Discoveries


A Python exporter could return one buffer for parsing and a different buffer
for payload views. Python 3.9 could also run a garbage-collection callback during
`feed()` and mutate a borrowed bytearray. These are input ownership defects;
AddressSanitizer did not diagnose the UTF-8 invariant violation. The regression
tests therefore check behavior as well as native memory errors.

The existing local check script compiled a Miri configuration for Clippy but
skipped actual Miri execution by default. Actual execution is now a separate,
documented command. Long, combined split-input cases were too slow under Miri;
short cases retain exhaustive split positions, while separate tests cover growth.

## Decision Log


2026-08-26: Base this work on upstream, since the scanner, ValueZipper, and
streaming Python binding already exist there. Keep it independently mergeable.

2026-08-26: Use Miri for Rust and AddressSanitizer plus behavioral regressions for
Python. Verify instrumentation with a deliberately invalid test library that is
never linked into the production extension.

2026-08-26: Snapshot mutable or unverifiable storage before Python callbacks can
run. Preserve borrowing of immutable bytes-backed storage. Unknown read-only
exporters remain accepted but their payloads retain an immutable snapshot.

2026-08-26: Add Python 3.9 to native CI because its synchronous garbage collection
exercises a defect that newer interpreters did not reproduce. Intern the `obj`
attribute name after measurements showed avoidable allocations.

2026-08-26: Reopen this plan for the user's upstream publication request. The
publishing account has read-only upstream access; project-label creation failed.

## Outcomes and Retrospective


Implementation and local validation are complete. Two Python ownership defects
were fixed without adding production unsafe blocks. Scanner assertions are
test/Miri-only. Bytearray input adds one snapshot allocation per chunk; measured
immutable-input allocation counts are unchanged. Shared-host timings do not
support a general speedup claim or a consistent slowdown.

Upstream publication and final hosted checks remain. Local results and coverage
limits are in `record.md`; passing tests are not proof of soundness.

## Context and Orientation


The scanner's unchecked conversions require valid UTF-8. ValueZipper caches
pointers into a boxed root, arrays, and ordered maps; old child pointers must be
discarded before ancestor storage moves. Python buffer guards retain native
storage, but read-only access does not establish immutable backing.

Miri executes Rust tests and checks certain invalid memory operations and
reference uses. Its Stacked Borrows and Tree Borrows models check overlapping
references. AddressSanitizer instruments native access checks but does not
check every Rust reference rule. CPython itself remains uninstrumented here.

## Plan of Work


The completed implementation adds test-only scanner assertions, dedicated
ValueZipper tests, and plain integration assertions that do not depend on
snapshot filesystem access. Python tests cover buffer release, retained views,
input mutations, and the two confirmed callback defects.

`.agent/check-miri.sh` runs the existing full suite and targeted configurations.
`.agent/check-py-memory.sh` builds a launcher and extension using the same Rust
sanitizer runtime, verifies an expected failure, and runs Python tests. CI calls
these scripts. Publication must retain this test coverage and its limitations.

## Concrete Steps


Run from this worktree:

    .agent/check.sh
    .agent/setup-py.sh
    .agent/check-py.sh
    cargo clippy -p jsonmodem-py -- -D warnings
    cargo test -p jsonmodem --release --lib memory_safety
    cargo test -p jsonmodem --release --test memory_safety
    bash .agent/check-miri.sh
    JSONMODEM_MEMORY_PYTHON=3.9 bash .agent/check-py-memory.sh
    JSONMODEM_MEMORY_PYTHON=3.13 bash .agent/check-py-memory.sh

The fastest Rust checks are `cargo test -p jsonmodem --lib memory_safety` and
`cargo test -p jsonmodem --test memory_safety`. The native script requires Linux
x86_64 and a shared libpython. Tool prerequisites are documented in `AGENTS.md`.

## Validation and Acceptance


All commands must pass without unexplained diagnostics. Keep the deliberate
sanitizer failure in its isolated subprocess; it is required evidence that
instrumentation works. Distinguish excluded crates, compiled-out tests, ignored
tests, and actual execution. Preserve baseline failures for production fixes.
After publication, inspect checks for the exact published head before marking
the PR ready. Do not bypass approvals or classify missing checks as passing.

## Idempotence and Recovery


Use this worktree's environments and target directories. Do not reset another
checkout or force-push. Keep full artifacts outside Git. For a failing command,
record whether the cause is a test failure, tool setup, or missing permission.
Do not suppress a memory error or disable reference checks to obtain a pass.

## Interfaces and Dependencies


Public Rust and Python entry points remain unchanged. Valid external exporters
are still accepted, with snapshots where immutability cannot be established.
Use existing PyO3, pytest, Miri, and native compiler tooling. Memray and pyperf
are development-only dependencies for the buffer comparison benchmark.

## Artifacts and Notes


`record.md` retains the source commits, reproducer results, validation commands,
timing and allocation tables, and publication status. Generated wheels, logs,
and allocator traces are not part of the upstream diff.

## Next Action


Push the branch to the user's fork and create the upstream draft PR. Check
whether fork workflows need maintainer approval, then verify required checks.
