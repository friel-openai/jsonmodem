# Hardened native acceleration

Status: implementation and measurements complete, based on PR #8. Publication
and required CI are tracked by the PR; this record does not claim CI approval.

## Purpose

Reduce Python serialization and parsing work while keeping the Rust parser's
incremental APIs and checked behavior. Reuse owning traversal and private output
builders. Native optimizations must establish their own type, layout, lifetime,
initialization, capacity and reentrancy requirements; callers must not promise
that arbitrary Python objects never change during a call.

## Work

1. Review CPython release history and comparable native-library code for every
   retained layout shortcut. Distinguish public APIs from private fields and
   manual object construction. Document supported versions and fallbacks.
2. Evaluate an owning-iterator numeric specialization independently of raw
   object access. Preserve integer ranges, float formatting, error priority,
   partial numeric runs, and rich-object fallback. Avoid reserving worst-case
   space for an entire list when only a small prefix may qualify.
3. Reuse shared JSON string classification and escaping functions. Add bounded
   SIMD only where exact input/output extents and CPU requirements are checked.
   Keep scalar behavior independently testable, including invalid text.
4. Keep borrowed operations free of Python calls and owner release. Own values
   before callbacks or Python allocation, and reacquire container storage after
   possible reentry. Publish only initialized, uniquely owned output.
5. Retain bounded immutable cache entries with owning references. Any cached
   mutable metadata needs complete invalidation and recursive-call isolation.
   Do not assume a dictionary version covers mutations inside its values.
6. Preserve the independent cached-zipper option, stable root, ancestor-pointer
   invalidation, and borrow-scoped references. Extend actual-source tests for
   any changed operation rather than substituting a model implementation.
7. Check PyO3's generated argument conversions before binding function entry.
   Use the pinned dependency patch for UTF-8 validation and codec-independent
   lossy error formatting. Require the patch in all builds, not just accelerated
   ones, and test keyword parsing and error-formatting reentry.
   Keep names and values owned through generated argument conversion, the Rust
   call and return conversion, including when a caller shares its keyword dict.

## Validation

Each candidate has a safety argument, targeted native tests and independent
measurement before integration. Run actual extracted Rust implementations under
Miri, with supported borrow models and execution seeds. Unsupported FFI or SIMD
operations remain explicit limitations. Use native sanitizer, debug-layout,
failure-injection and callback tests for those operations.

Preserve the full Rust/Python suites, feature combinations, ordinary and portable
calls, precise error behavior, and incremental streaming results. Enabling an
optimization must never turn off validation. Positive Cargo features select
implementations; per-call portable choice remains effective after feature
unification. Neither option promises an unsafe-free dependency graph.

Measure the unchanged base, each candidate and the final combination using the
same package identities and inputs, with rotated fresh-process order. Include
maintained complete-call cases, public corpora, streaming, cache misses and
fallback, Memray and separate RSS. Report absolute units, geometric means,
every regression and any unequal-output exclusion. Do not transfer timing from
one implementation to another after hardening.

## Progress

- [x] Create an isolated worktree based on the published PR #8 commit.
- [x] Research and document CPython layout/API stability and analogous library use.
- [x] Implement and measure bounded numeric and string candidates separately.
- [x] Integrate qualified traversal, construction and cache improvements.
- [x] Complete native, Miri, feature and streaming qualification.
- [x] Prepare the measured results and source for a separate labeled PR.

Publication must use a draft PR stacked on #8, labeled `jsonmodem`. Mark it
ready only after required checks pass on its exact final commit. Do not merge.
The PR's live checks track this release requirement; the committed plan records
the completed implementation and measurements rather than a stale CI snapshot.

## Outcome

Keep owning argument snapshots, checked text conversion and the shared bounded
classifier. Reject numeric specialization and eight-escape batching. The
275-case mean takes 0.3% more time than PR #8 and 31.9% more than orjson 3.11.9.
Long-string decoding improves, but two root-string encoding cases regress
about 28%. All 45 incremental traces match and their overall timing is
essentially unchanged. Memray and RSS show different tradeoffs, retained in
the report. Native tests, sanitizers and Miri establish the recorded checks,
not a universal memory-safety proof.

## Evidence

record.md records implementation decisions, public sources, tests and measured
results. Keep the original PR #8 implementation and report unchanged.
