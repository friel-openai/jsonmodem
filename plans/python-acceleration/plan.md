# Optional Python encoding acceleration

Implementation and measurements are complete and published in
[PR #8](https://github.com/friel-openai/jsonmodem/pull/8), stacked on PR #7.
Required checks on the final PR commit must pass before the PR is marked ready.
GitHub records that final CI result and review state.

## Purpose

Reduce repeated work during Python serialization without changing the Rust
parser or weakening its input checks. The first change caches validated offsets
of exact built-in timezone objects for one serialization call. A separate
experiment uses initialized stack storage for short primitive output and moves
to a Vec once it grows. Retain that experiment only if measurements justify it.

The Python crate's positive `python-acceleration` Cargo feature controls these
new implementations. `jsonmodem.portable.dumps` keeps the ordinary encoding
behavior available in a feature-enabled build. Its selection is local to the
call; it does not modify process-wide configuration. Existing `loads`, streaming
APIs and the core crate's `cached-zipper` feature are unchanged.

## Progress

- [x] Read the existing output ownership, datetime and callback implementations.
- [x] Implement the owning fixed-offset cache and per-call portable selection.
- [x] Add cache, callback, helper-replacement and portable-selection tests.
- [x] Build and run focused Rust and Python tests.
- [x] Reject the independent inline-output experiment on repeated timing losses; record its memory savings separately.
- [x] Run default, feature-disabled and forced-portable Python checks.
- [x] Run the actual Rust components under Miri and native Python memory checks.
- [x] Measure retained changes and controls, including streaming and memory.
- [x] Document actual results and limitations, then publish a separate PR.

## Context

`crates/jsonmodem-py/src/compat.rs` handles common Python values without streaming
events. `compat/objects.rs` owns container entries before callbacks and delegates
built-in date/time formatting to `compat/objects/datetime.rs`. The existing
`compat/output.rs` owns output storage and distinguishes Rust allocation from
Python allocation. Preserve that distinction and the owning callback behavior.

`compat/fixed_offsets.rs` holds at most eight owned keys with integer offsets.
It contains only safe Rust. The Python caller supplies a live timezone owner
and only inserts after validating an exact built-in timezone and exact
`timedelta` and string name. A cache disabled at construction neither evaluates
entry construction nor retains owners. Sixteen consecutive misses disable
further lookup and insertion but retain existing owners until the call ends.
Root datetimes do not use the cache. Each `ObjectEncoder` owns its own cache.

The validation crate includes the actual cache source without linking Python.
This permits Miri to exercise its bounds, moves, failures and owner releases.
It does not let Miri verify PyO3 or CPython. Native tests must cover those calls.

## Work

First preserve exact datetime formatting, options, callback order and helper
replacement behavior. Use `test_python_acceleration.py` together with the
existing datetime and owning-output tests. Cache entries must not admit custom
timezones or timedelta subclasses. Equal offsets on distinct timezone objects
must not confuse identity checks. Reentrant calls must have independent caches.

Expose the existing public API through `jsonmodem.portable`, changing only its
`dumps` function. Package-owned recursive key conversion must preserve that
choice; explicit user helper replacements retain their ordinary signature and
behavior. Test this even when all Cargo features are enabled. Cargo feature
unification can enable a dependency feature, so disabling defaults in one
dependency declaration is not a process-wide opt-out.

Evaluate stack-first primitive output separately. It must keep initialized
storage, checked bounds, one-time transfer to Vec storage, and the existing
rich-object restart and Python-byte publication rules. It must not change
number formatting or introduce a raw pointer to an inline array. Test the actual
implementation in the Rust validation crate before considering integration.

Finally compare retained implementations with an unchanged base build and
orjson on the same machine. Measure short calls, repeated and distinct
timezones, cache misses and eviction, larger output, callbacks and the broader
complete-call suite. Run streaming controls to check that unchanged parser
behavior remains intact. Use exact output checks before timing, fresh processes,
balanced process order, fixed input and package identities, and no overlapping
builds or profiling. Keep failed attempts and every timing observation.

## Validation and acceptance

Run `.agent/check.sh` with the repository's quick-feedback environment variables
during development, and compile the fuzz crate with the command in `AGENTS.md`.
Run `.agent/check-py.sh` for the binding suite. Exercise the default build,
`--no-default-features`, and feature-enabled portable calls separately.

Run `.agent/check-miri.sh` for the workspace and targeted checks. Include each
new pure Rust implementation unchanged under both supported borrow models and
multiple seeds. Run `.agent/check-py-memory.sh` with the optional dependencies
installed when claiming NumPy or reference-library coverage. Record interpreter
and sanitizer limitations rather than treating a skipped test as a pass.

All correctness and ownership checks must pass before default enablement.
Performance acceptance requires repeatable benefit on the targeted cases and
an explicit account of broader regressions and memory costs. Report absolute
times in tables marked "lower is better", highlight the best value in each row,
and give equal-case geometric means. Do not inherit performance claims from
another implementation or compare timings from different machines as paired data.

## Decisions

The new Cargo feature controls additional Python encoding work only. The
portable implementation still uses existing native code and dependencies; it
does not promise an entirely unsafe-free dependency graph. Both selections
must remain memory-safe and preserve the supported API.

Keep the current output publication policy. A stack-first buffer and publication
without shrinking are different changes with different memory costs. The latter
is outside this implementation.

## Surprises and discoveries

The first cache's extra root-datetime allocations and repeated miss costs were
measured, then reduced by skipping roots and stopping after sixteen misses.
The selected cache retains short miss penalties and unrelated regressions;
`record.md` and the benchmark report preserve them. The inline-output experiment
reduced allocations but increased aggregate time, so it was rejected.

## Outcomes and retrospective

The selected cache adds no handwritten unsafe code and leaves the Rust parser
unchanged. It passes the native and extracted-kernel checks and improves the
275-case complete-call mean by 1.5%, but remains 36.9% slower than measured
orjson 3.11.9. PR #8 contains the implementation and complete benchmark report.
`record.md` records the validation limits, regressions and reasons for retaining
the optional cache. Final-head CI remains a condition of marking the PR ready;
these local results do not substitute for it. No merge is part of this work.
