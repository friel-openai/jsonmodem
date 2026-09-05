# Hardened acceleration evidence

The starting implementation is commit
`c9ab60b4a6ecb28ed800f4e5f23953175c41613f` from PR #8. Complete-call and streaming
timing are recorded below. The [full report](../../crates/jsonmodem-py/benchmarks/HARDENED_ACCELERATION.md)
includes memory results and every benchmark observation.

## First candidate: owning numeric iteration

The primitive list loop currently dispatches each number through the general
scalar encoder. Test a numeric prefix loop using the same owning PyO3 iterator
and checked integer conversion. Stop specialization at the first other type,
without losing that item or repeating its encoding. This introduces no new
pointer access, object layout, whole-list reservation, or Python callback.

Compare integer and float lists, short and full-width values, numeric prefixes
followed by strings/containers/callback objects, strict-integer errors, tuples,
indentation, and portable calls. Preserve exact outputs and error order. The
candidate is not accepted merely because its code has fewer type checks.

The numeric specialization was rejected after three comparisons: it increased
overall call time and integer-output time. The implementation was removed; its
224 correctness cases remain. Detailed timing results will accompany the final
comparison rather than treating this rejected candidate as a shipped gain.

## Argument lifetime and checked text

The dependency patch checks UTF-8 before generated PyO3 argument conversion can
create a Rust string. A separate ownership fix retains keyword names and values
through conversion and the Rust call. A caller can clear a shared keyword
dictionary during a codec handler or an argument conversion; owning the
dictionary alone would not keep its former entries alive.

The generated wrapper holds an immutable Rust snapshot with a borrow lifetime
checked by Rust. Tests use weak references and stop before reading a potentially
freed value in an unpatched implementation. Free-threaded builds are not
supported. Native compilation passed. All three ownership cases fail on the
preceding binding with a premature-destruction assertion and pass with the fix.
The full native, sanitizer and Miri results are recorded below. Complete-call
and streaming timing, allocations and RSS are measured.

## String scanning

The bounded classifier reduced total call time in each of three comparisons
against its immediate parent. Keep it for final combined measurement. The
eight-escape decoder increased dense escaped-string decoding time by 56-62%
and made the string family slower. Remove that decoder and its dedicated
kernel tests; retain the parser's consecutive-escape content/error tests.

## Native and source-distribution checks

On CPython 3.12, the default, portable and feature-disabled runs each passed
16,280 tests and six subtests. The focused debug-allocator run passed 339 tests.
The ASan build passed 16,277 tests and six subtests; the focused portable ASan
run passed 851 tests. The deliberate invalid-access test produced the expected
ASan diagnostic, and the compiled extension contains the ASan initialization
symbol.

ASan skips the three parameter cases of
`test_array_allocation_failure_is_catchable`: that test uses Linux virtual-
address limits, which conflict with ASan's shadow-memory reservation. Those
cases passed in the three ordinary builds. No test or assertion was removed
for this change. Sanitizer results do not establish safety for arbitrary native
buffer providers or CPython's uninstrumented implementation.

The core check passed formatting, Clippy, documentation, all eight feature
combinations and workflow linting. Fuzz targets compiled. Final CI remains
a separate requirement.

The source-distribution check found and fixed missing local dependencies and
Cargo's reserved `Cargo.toml.orig` filename. Maturin now includes both patched
dependencies. Building the extracted archive preserves dependency versions,
sources, checksums and resolved relationships; only unused workspace lockfile
entries are removed. All 239 local Rust compilation files match the source used
for native checks. The resulting wheel passed the full default and portable
Python suites. This verifies a build from the archive, not just archive creation.

## Miri checks

All 24 commands passed, covering 60 test executions. Each command ran either
the four classifier tests or the consecutive-escape parser test. Both portable
and SIMD implementations ran under Stacked Borrows and Tree Borrows, Miri's
two supported models for checking pointer access, with three execution seeds.
The SIMD runs executed the actual SSE2 intrinsics, not a scalar replacement.
The checked Rust source matches the source used for native validation and the
archive-built wheel.

The tests exercise every byte value in every SIMD position, adjacent special
characters, alignment, and allocation ends. They check the memory operations
on those inputs; they do not prove the whole parser correct. Miri does not run
CPython's C implementation. The native and sanitizer checks above cover a
different set of risks, including callbacks, argument lifetime, and failure
cleanup.

## Complete-call timing

The final archive-built package was compared with an unchanged rebuild of
PR #8 and upstream orjson 3.11.9 in three fresh-process orders. All 275
included cases have matching outputs. Three pre-existing unequal-output date
cases remain outside the mean. Every case has equal weight; each case's time
is the median across the three processes. The orjson column uses the median
of the paired controls. Microseconds per call; **lower is better**.

| Suite | PR #8 | Hardened | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| All 275 comparable cases | 57.427 | 57.600 | **43.677** |
| Output | 82.254 | 81.718 | **46.960** |
| Frontend | 28.894 | 29.514 | **22.250** |
| Numbers | 51.386 | 52.087 | **41.787** |
| Strings | 35.695 | 35.282 | **26.611** |
| Dates | 20.428 | 20.285 | **15.609** |
| NumPy | **22.253** | 22.605 | 28.445 |
| Public documents | 2,065.870 | 2,064.424 | **1,262.043** |

Hardened takes 0.3% more time than PR #8 and 31.9% more than measured orjson.
Adjusting each process by its paired orjson control gives changes of -0.40%,
+0.03%, and +0.02% from PR #8. The aggregate is essentially unchanged;
this is not an overall speedup. orjson 3.12.0 was not measured.

The aggregate hides larger changes. Microseconds per call; **lower is better**.

| Input | PR #8 | Hardened | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode long escaped string from bytes | 83.019 | **73.353** | 88.535 |
| Decode long plain string from bytes | 25.758 | **23.433** | 78.354 |
| Encode densely escaped root string | **97.084** | 123.992 | 321.934 |
| Encode root string with BMP characters | 126.358 | 161.164 | **5.964** |
| Decode repeated escaped keys | 160.428 | 175.327 | **113.381** |
| Encode sixteen-field dataclasses | 877.971 | 888.222 | **357.219** |
| Encode late default callback | 13.196 | 12.703 | **3.173** |
| Encode public `otfcc` document | 858,787.653 | 890,662.119 | **397,803.411** |
| Decode public `otfcc` document | **2,270,848.350** | 2,327,083.900 | 3,821,793.691 |

BMP means the Basic Multilingual Plane: Unicode characters with code points
up to U+FFFF. The two root-string encoding regressions are roughly 28%.
The long-string decoding improvements and both root-string regressions occur
in every process order. The final comparison combines required text and
argument-lifetime fixes with the shared classifier; it does not isolate each
change's latency cost. Keep the safety fixes and report their combined result.
Allocation and RSS results are summarized below and included in the full report.

## Incremental parsing

All 45 fixtures have matching event/value traces, inputs and chunk boundaries.
They cover records, numbers and Unicode with 16-, 64- and 256-byte chunks.
Each row gives every included case equal weight in a geometric mean.
Microseconds per operation; **lower is better**.

| Operation | PR #8 | Hardened |
| --- | ---: | ---: |
| All 45 cases | **492.106** | 492.540 |
| Events | **333.551** | 334.196 |
| Minimal events | 252.562 | **252.443** |
| Tracked events | **334.600** | 334.957 |
| Values | 468.339 | **464.586** |
| Prefix snapshots | **2,186.119** | 2,207.944 |

Overall time is essentially unchanged: the 0.09% increase is smaller than the
variation between process orders. The largest per-case median regression is
numeric prefix snapshots with 16-byte chunks: 4,976.763 to 5,209.799 us, or
4.7% more time. Unicode events with 16-byte chunks improve from 298.439 to
285.754 us, or 4.3% less time. No overall streaming speedup is claimed.
orjson has no equivalent incremental event API and is not compared here.

## Memory and outcome

Memray 1.20.0 recorded thirty calls after ten warmup calls for twelve fixtures.
PR #8, hardened, and portable mode had identical allocation counts, total
allocated bytes, and peak live bytes in these fixtures. Keyword-argument
snapshot construction is not among those fixtures. JSONModem's peak live
allocation is lower than orjson in nine cases and higher in three: integer
lists, sixteen-field dataclasses and late-default output.

Separate RSS processes retained thirty results without Memray. Hardened has
higher RSS than upstream orjson in eight of twelve fixtures. Imports and input
preparation are included; RSS does not isolate serializer memory. Each cell
is one observation. The report includes absolute values and full CSVs rather
than interpreting small RSS differences as repeatable improvements.

Retain the safety fixes and shared classifier. The independently measured
classifier improves long-string decoding; the complete implementation leaves
overall and incremental timing essentially unchanged while retaining the
reported encoding regressions. Remove both rejected numeric and eight-escape
implementations. No source changes followed final qualification; later edits
are documentation and generated measurements. Final approval remains subject
to the PR's required CI checks, including interpreter configurations not run
in the CPython 3.12 qualification above.
