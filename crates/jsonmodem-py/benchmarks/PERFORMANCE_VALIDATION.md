# Validation of the performance changes

The local checks below tested runtime source at `b0f3190`. Benchmark results
use the Python 3.12 release package from those checks. The later publication
commit `44d9008` changes only adjacent-escape test collection, allowing those
tests to run without an installed orjson reference. It does not change the
compiled implementation. The 198 affected tests were rerun on all six
validated packages and passed without skips.

## Python checks

Counts below describe the complete runs before that test-collection change.
The additional 198-test runs are separate and must not be added to these
counts as though they were distinct tests.

| Interpreter | Release passes | Release reported skips | AddressSanitizer passes | AddressSanitizer reported skips |
| --- | ---: | ---: | ---: | ---: |
| Python 3.9 | 2,529 | 873 | 2,526 | 876 |
| Python 3.12 | 3,865 | 0 | 3,862 | 3 |
| Python 3.13 | 3,865 | 0 | 3,862 | 3 |

Each Python 3.12 and 3.13 run also reports six passing subtests. Python 3.9
cannot install the pinned orjson 3.11.9 release, so its reference-dependent
tests are skipped. The separate adjacent-escape run closes that test file's
unnecessary dependency on orjson; it does not supply the other missing
reference comparisons. The 227 new error-position tests passed on Python 3.9.

The three additional sanitizer skips use process address-space limits that
conflict with AddressSanitizer. A deliberate memory fault was detected as a
positive control for every sanitizer package. The runner instruments the
extension and launcher, not CPython, the prebuilt Rust standard library or
the orjson wheel, and disables leak detection.

The Python checks include the API, security and benchmark-tool tests. A
separate untimed check validates outputs for all 43 date/time and 28 NumPy
datetime64 fixtures. Three known time-fraction differences are checked
against explicit expected outputs rather than treated as equivalent.

## Reference release tests

The unchanged [orjson 3.11.9 release tests](https://github.com/ijl/orjson/tree/705515d77b28429d0b7c30c3d781abe52e8a1e5a/test)
ran first against orjson and then against jsonmodem's compatibility API.
The control passed 1,630 tests; jsonmodem passed 1,626. Both reported the same
six upstream skips. Only four assertions about package name or version were
excluded for jsonmodem.

The six skips cover an unconfigured huge-buffer test, two tests requiring
pandas, an upstream float32-equivalence test, and two unsupported-input tests.
Passing this release suite is not a guarantee of equivalence for every object
or of compatibility with unmeasured orjson 3.12.0.

## Rust and documentation

The repository checks passed formatting, Clippy, documentation, bindings
checks, workflow validation and 219 Rust tests. Four existing debug-helper
tests were ignored. Python documentation generation also passed.

Actual Miri execution passed the Rust workspace suite: 210 tests passed and
four existing tests were skipped. It also passed six combinations of
reference model and random seed, each running the same ten targeted tests,
and three SIMD target-feature configurations, each running four tests.
These repeated executions are not additional distinct test cases. Miri and
the Rust fuzz targets exclude the Python binding.

## Failed attempts and scope

The first Python 3.13 release attempt passed its API tests but failed the
strict report check because the Memray benchmark-tool test was skipped.
Installing the pinned profiler in that test environment and rerunning with
the same wheel produced the complete passing result above.

The first reference-suite attempt failed eleven process-memory checks
because its Python PID and mounted process filesystem used different PID
namespaces. Running the unchanged suite with matching process information
produced the passing control and compatibility results above. No test was
removed or weakened for that rerun.

The [safety comparison](IMPLEMENTATION_SAFETY.md) explains remaining unsafe
dependencies, native-buffer assumptions, resource limits and callback
ownership. Sanitizer and Miri success establish what happened in those
executions, not a proof that either library is memory-safe for all inputs.
