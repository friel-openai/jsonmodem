# Validation of the corrected build

These results apply to runtime revision
`96318df6102bf40e30383125f77fa300ca236047`. Benchmark data record the source
and native-library hashes separately. Later test-only corrections do not
change that measured runtime.

## Python tests

These are pytest-reported counts, not distinct tests across interpreters.
Python 3.9's skipped total includes whole modules skipped during collection.

| Configuration | Passed | Failed | Passed subtests | Skipped |
| --- | ---: | ---: | ---: | ---: |
| CPython 3.12.13 release | 15,945 | 0 | 6 | 0 |
| CPython 3.13.14 | 15,945 | 0 | 6 | 0 |
| Debug CPython 3.12.13 | 15,945 | 0 | 6 | 0 |
| AddressSanitizer with CPython 3.12.13 | 15,942 | 0 | 6 | 3 |
| CPython 3.9.25, original test expectations | 11,652 | 20 | Not separately reported | 1,795 |

The Python 3.9 failures came from two new callback tests that assumed Python
3.12's lookup order. The root-container optimization is disabled on Python
3.9. The corrected tests compare container encoding with scalar-by-scalar
encoding, including callback arguments and order, in fresh processes. All
twenty variants then passed on each of the five configurations above, with
no skips. These focused checks do not turn the earlier full-suite failure
into a full-suite pass.

Python 3.9 lacked orjson and Memray. Its skips include twelve modules skipped
during collection, 1,777 cases requiring orjson, one requiring Memray, and
five requiring newer buffer methods. Comparisons requiring those missing
dependencies remain untested on Python 3.9.

ASan skipped three address-space-limit tests because its shadow memory is
incompatible with those limits. A deliberately invalid library produced the
expected heap-buffer-overflow diagnostic. Separately, all 400 output-buffer
allocation-failure and recovery iterations passed. ASan instrumented the
extension and launcher, not CPython or most dependencies; leak detection
was disabled.

## Rust and native checks

All four combinations of `cached-zipper` and `serde` passed 251 core tests,
with six existing ignores per configuration. The Python-independent binding
tests passed 41 tests. The native extension tests passed 88, with five
default ignores. Formatting, Clippy, documentation and fuzz-target compilation
passed.

The existing NumPy/date allocation-failure test and four new NumPy
root-container admission and allocation-failure tests were explicitly enabled
and passed. These tests are ignored by default; an ordinary suite pass does
not establish their coverage.

Additional tuple-ownership checks passed three tests on Python 3.9, four on
Python 3.13, and three on debug Python. Python 3.9 and debug builds exclude
the allocation-failure variant. All four separately instrumented ASan tuple
checks also passed.

## Miri

All 281 selected workspace tests passed across an interrupted run and a
focused continuation. Four existing tests remained ignored. The first attempt
hit the five-minute limit on six long-number tests. With a longer limit for
`number::tests` only, 279 tests passed before SIGTERM interrupted the last two.
The signal's sender was not recorded. Those two tests then passed with the
same source and inputs; neither earlier attempt is a complete passing run.

The seventeen additional commands also passed:

- Library and integration checks used seeds 0, 1 and 2 under the repository's
  default borrow checking and explicit Tree Borrows. Each configuration passed
  eleven library tests and four integration tests.
- Without `cached-zipper`, four traversal tests passed under each borrow
  setting with seed 2.
- The Python-independent helpers passed 41 tests in each of three SIMD
  configurations: SSE4.2, AVX2 and AVX-512.

The final continuation's source hashes, output hashes and process cleanup
records were checked separately. No test input was shortened or removed.
Long-number tests now have a sixty-minute Miri limit; the other limits are
unchanged. CI allows two hours for the full suite and targeted checks.
Miri does not execute the live CPython extension.

## Numeric regressions and limits

The corrected build passes the long-number underflow, overflow and exponent
cancellation regressions through `loads()` and the streaming APIs. A number
with 268,435,456 zero digits and exponent `-2684354560` returned `1.0` on the
earlier build; the corrected build and orjson return positive zero. This
replay is a correctness test, not a timing or memory comparison.

Overflow errors can still report different character offsets from orjson.
The measured reference is orjson 3.11.9; version 3.12.0 was not measured.

The [safety documentation](../../../../../docs/memory-safety-testing.md)
states the ownership, initialization, GIL and storage requirements for the
unsafe operations. Local Unicode conversions now check UTF-8. PyO3-generated
argument handling and error formatting still contain unchecked conversions
outside that fix. These tests do not establish memory safety for every Python
entry point, valid storage from a malformed native exporter, or complete
orjson equivalence.
