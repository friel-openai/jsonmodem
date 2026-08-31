# Python performance: large documents and worst cases

This change reduces time across the public-document suite, but **does not
surpass orjson overall**. The reference is **orjson 3.11.9** on CPython
3.12.13. **orjson 3.12.0 was not measured.**

## Complete calls

Four builds appear in the tables:

- **Original:** the previous measured jsonmodem from [PR #4](https://github.com/friel-openai/jsonmodem/pull/4), runtime `b0f3190`.
- **Rebuilt:** the same previous runtime, freshly compiled from `3279ba1`.
- **Final:** this PR's optimized runtime, `b889f4c`.
- **orjson:** the installed 3.11.9 wheel.

The two previous builds expose differences between compilations of unchanged
runtime code. Neither control is discarded when it gives a less favorable
comparison.

Public documents: geometric-mean latency in **microseconds per complete call;
lower is better**. Bold marks the smallest unrounded value in each row.

| Suite | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| 18 decoding cases | 2,351.524 | 2,352.985 | 2,220.319 | **1,560.490** |
| 18 encoding cases | 1,038.946 | 1,038.833 | 883.634 | **473.640** |
| All 36 cases | 1,563.043 | 1,563.444 | 1,400.696 | **859.715** |

Compared with Original, Final takes 5.6% less time to decode and 14.9% less
time to encode. Every public case has a lower median than both previous
builds. Each library ran in eight fresh Python processes. Twenty cases improve
by more than 3% in every repeat against both controls. Only one of the 36 cases
beats orjson, and that win
already existed: decoding `gsoc-2018`.

The largest document, `otfcc`, still leaves a large gap. Absolute latency in
**milliseconds per complete call; lower is better**:

| Operation | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| Decode `otfcc` | 1,103.189 | 1,100.705 | 1,071.926 | **785.046** |
| Encode `otfcc` | 378.658 | 381.365 | 288.694 | **119.193** |

Four public cases still take more than twice orjson's time: encoding
`citm_catalog`, `github_events`, `tree-pretty` and `otfcc`.

The maintained, date/time and NumPy runners measure orjson alongside each
jsonmodem build. The two orjson columns below are separate observations of
the same version, not different versions or pooled results.

Comparison with Original: geometric-mean latency in **microseconds per
complete call; lower is better**. Bold uses unrounded values.

| Suite | Original | Final | orjson, Original runs | orjson, Final runs |
| --- | ---: | ---: | ---: | ---: |
| Maintained decoding, 106 cases | 39.283 | 36.067 | **32.732** | 32.830 |
| Maintained encoding, 65 cases | 23.571 | 22.045 | **15.693** | 15.814 |
| Maintained combined, 171 cases | 32.351 | 29.911 | **24.752** | 24.871 |
| Date/time, 40 equal-output cases | 21.181 | 18.710 | **11.687** | 11.742 |
| NumPy datetime64, 28 cases | 21.043 | **20.964** | 22.945 | 23.008 |

Comparison with Rebuilt: geometric-mean latency in **microseconds per
complete call; lower is better**. Bold uses unrounded values.

| Suite | Rebuilt | Final | orjson, Rebuilt runs | orjson, Final runs |
| --- | ---: | ---: | ---: | ---: |
| Maintained decoding, 106 cases | 39.351 | 35.985 | **32.766** | 32.796 |
| Maintained encoding, 65 cases | 23.793 | 22.054 | **15.759** | 15.759 |
| Maintained combined, 171 cases | 32.501 | 29.874 | **24.808** | 24.822 |
| Date/time, 40 equal-output cases | 21.206 | 18.696 | 11.750 | **11.725** |
| NumPy datetime64, 28 cases | 21.102 | **20.864** | 22.860 | 23.005 |

The maintained suite takes 7.5% less time than Original and 8.1% less than
Rebuilt, but remains about 20% slower than orjson overall. Final beats its
paired orjson median in 45 of 171 cases in the Original comparison and
44 in the Rebuilt comparison; these are observed case medians, not claims
of a statistically established lead in each case.

Date/time improves by 11.7-11.8% against the controls but still takes about
59% longer than orjson. NumPy datetime64 retains its existing lead, taking
about 9% less time than orjson. Neither focused suite has a case median more
than 3% slower than either control.

The date/time suite includes UUID and ordinary-container controls; it is not
a score for calendar formatting alone. In its 1,024-UUID case, time falls
from 907.954 to 80.079 us against Original, versus 45.854 us for orjson.
The Rebuilt comparison gives 905.233 to 79.972 us, versus 45.955 us for orjson.
The UUID controls contribute much of the aggregate improvement. A single
UUID still takes about 0.65 us, versus orjson's 0.23 us.

A geometric mean gives each case equal weight; it does not estimate
application traffic or the time to run the cases in sequence. The public,
maintained, date/time and NumPy suites have separate means. Preparation and
correctness checks are outside timing; result destruction is included.
These are repeated calls on reused inputs, not first-use measurements.

The [18-document corpus](PUBLIC_CORPUS.md) comes from collections used by
simdjson, yyjson and other JSON parsers. Its selection and pinned hashes
predate these optimizations. All 171 maintained cases remain in their suite.
Three date/time cases have known byte differences from orjson 3.11.9 and are
shown separately, not scored as cross-library wins. orjson omits a leading
zero from some time fractions; jsonmodem retains the padding used by
`datetime.time.isoformat()`. That leaves 40 comparable date/time cases and
28 NumPy cases.

## Remaining gaps and regressions

Suite averages hide larger gaps. Selected case medians from the Original
comparison, **microseconds per complete call; lower is better**:

| Case | Final | orjson |
| --- | ---: | ---: |
| Decode unique escaped keys | 143.339 | **36.870** |
| Encode sixteen-field dataclasses | 773.803 | **305.869** |
| Encode a NumPy datetime64 scalar, day units | 3.083 | **0.869** |

NumPy's aggregate lead comes from arrays, not these scalar cases.

Thirteen maintained cases regress by more than 3% against at least one
control; nine regress against both. Sorted output and decoding a short
plain byte string regress by more than 3% in every repeat against both controls.
Sorted output takes about 11% longer, and short-string decoding about 10%
longer. Short-string decoding nevertheless remains faster than orjson in
this case.

Other losses include tiny integer output, a late `default` callback,
sixteen-field dataclasses, scalar integer decoding, random small-integer
output and short-string buffer inputs. Dense escapes and a late escape also
regress in the Original comparison. The complete tables retain every case.
The selected combination favors the broader gains; it does not improve
every workload.

All individual measurements, including slower cases, are in the complete
tables below. Timing on this shared host is not proof of a speedup on other
machines. Earlier investigations found repeatable differences between
identical extension files without establishing their cause; retaining both
controls does not eliminate that limitation.

## Malformed input and memory

The 1 MiB late-syntax-error case falls from 25.19 ms to 3.30 ms, an 86.9%
reduction against Original. It still takes 1.77 times orjson's time.
No rejection case has a median more than 3% slower than either control.
Seven of the 39 rejection cases have a lower median than orjson.

Selected rejection latencies in **microseconds per call, including exception
handling; lower is better**. Bold uses unrounded values.

| Invalid input | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| Early syntax error, 1 MiB | 126.795 | 126.476 | 93.760 | **85.505** |
| Late syntax error, 1 MiB | 25,191.851 | 24,629.321 | 3,304.852 | **1,862.471** |
| Unfinished string, 1 MiB | 564.902 | 564.090 | **548.502** | 762.643 |
| Depth limit, 1,025 nested arrays | 31.412 | 32.278 | 30.864 | **3.912** |

Depth-limit rejection remains a large relative gap. Rejection measurements
have no geometric-mean or throughput score and do not enter the successful
parsing scores. An early rejection need not examine every input byte.

All three Memray counters are unchanged against both controls in all 36
public cases and all 14 synthetic allocation cases. The public speedups
remove conversion and iteration work, not these allocations.

For `otfcc` decoding, jsonmodem makes 10,276,965 allocation requests versus
orjson's 7,375,455. Fewer requests do not necessarily mean fewer bytes:
jsonmodem's peak tracked allocation is lower. The opposite holds for encoding.

Peak live tracked allocations in **MiB; lower is better; not RSS**. The
three jsonmodem builds have identical values here. Bold uses unrounded values.

| Workload | jsonmodem, all three builds | orjson |
| --- | ---: | ---: |
| Decode `otfcc` | **585.970** | 1,225.442 |
| Encode `otfcc` | 127.334 | **64.000** |

Peak process RSS, **MiB including preparation; lower is better**:

| Workload | Final | orjson |
| --- | ---: | ---: |
| Decode `otfcc` | **707.668** | 871.754 |
| Encode `otfcc` | 713.957 | **713.285** |
| Decode `canada` | **34.102** | 41.223 |

Lower peak RSS does not mean a smaller retained result. For `otfcc` decoding,
RSS while the first result is alive is 707.590 MiB for Final and 582.469 MiB
for orjson. Their prepared RSS values are 86.172 and 85.473 MiB. For encoding,
more than 521 MiB is already resident before either library starts. These
totals must not be presented as memory allocated solely by a serializer call.

Selected allocation requests, **one call after ten warmups; lower is better**:

| Workload | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| Encode 1,024 UUIDs | 12,313 | 12,313 | 22 | **17** |
| Late syntax error, 1 MiB | 262,083 | 262,083 | 29 | **28** |
| Depth limit, 1,025 nested arrays | 983 | 983 | 983 | **28** |

UUID encoding removes temporary allocations, but encoding 1,024 UUIDs still
peaks at 103.611 KiB of tracked memory versus orjson's 64.610 KiB. Its peak
RSS is 28.105 versus 27.316 MiB; both already reach those values during
preparation. Allocation reduction is not a demonstrated RSS reduction.
The other 41 date/time cases and all 28 NumPy cases have unchanged Memray
counters against both controls.

Late-error rejection avoids constructing Python values for the invalid
document. Its peak tracked memory falls from 25,676.862 to 1,025.401 KiB,
below orjson's 12,292.570 KiB. Depth-limit rejection does not get the same
benefit: it still constructs the permitted outer lists before rejecting
the next one.

Memray measures allocation requests, total requested bytes and peak live
tracked bytes during a call. Its peak is **not RSS**. Requests and requested
bytes were recounted from the saved captures; tracked peaks use Memray's
metadata. Reallocations contribute their full requested size.

RSS comes from separate fresh processes. Peak RSS includes the interpreter,
imports, input preparation and allocator retention. Prepared RSS and RSS
while the first result is alive are separate current-memory readings, not
peaks. No rejection RSS or memory geometric mean is reported.

The complete memory tables use one metric per table, one workload per row
and one column per library. Every table states its units and that lower is
better. [The measurement commands](PERFORMANCE_24H_REPRODUCTION.md) explain
warmups, process order, capture limits and which stages lack a public
command-line coordinator.

## What changed

- Ordinary unsorted dictionaries avoid temporary Python owners for supported
  primitive entries. Dense string-key tables use direct reads. Other layouts
  retain the existing iteration; callbacks still retain container entries
  before calling Python.
- Exact supported Python integers and ASCII strings use checked CPython
  representations instead of repeated conversion calls.
- A 16-byte SIMD mask finds multiple escapes in one block. Encoded-key reuse
  skips lookups that cannot match. When a long root string needs escaping,
  its initial plain text is copied in 1,024-byte chunks.
- Decoding carries the scanner's ASCII classification into Python string
  construction rather than checking the same immutable text again.
- Decoded arrays fill spare list capacity directly. The decoder reads current
  storage after constructing each value, initializes its slot, then updates
  the length. CPython still handles growth.
- Selected invalid container endings are validated without constructing all
  Python values. Large ASCII error documents use checked string allocation,
  with `MemoryError` propagated on failure.
- Exact UUIDs format into an initialized Rust byte buffer. Their integer
  getters and conversion failures retain the required exception behavior.

These changes keep grammar, UTF-8, integer, depth and ownership checks.
`loads()` still avoids streaming events and path copies. The incremental
parser remains available. Ordinary container output still uses an initialized
Rust buffer and a final copy into Python `bytes`. Long unescaped root strings
retain their existing direct Python-bytes allocation. Root NumPy output can
also reuse its already completed bytes. This PR does not remove the general
container-output copy.

Incremental measurements remain separate. The numeric event cases stay
within 3% of both controls, but some byte-view cases are slower. For example,
wide unsigned byte-view events take 429.675 us versus Original's 411.507 us.
Long-string byte-view events take 633.069 versus 609.390 us against Original,
and 637.819 versus 620.945 us against Rebuilt. These losses are retained.
The string-stream allocation requests and tracked peaks are unchanged.
No overall incremental speedup is claimed.

## Profiles and safety

[Final CPU profiles](PROFILE_24H.md) still show dictionary operations,
list and float construction, string scanning and the final output copy.
The late-error recording reports 130 sampler errors, so its function counts
are not reliable proportions of runtime. Speedup claims use the separate
uninstrumented timings and allocation measurements, not profile call counts.

**This PR adds unsafe code.** It reads CPython object layouts, writes owned
list slots, initializes Python string storage and loads checked 16-byte
blocks for SIMD. Each operation has documented platform, ownership and
allocation rules. The object-layout shortcuts are restricted to supported
GIL-enabled CPython builds; other builds retain the PyO3 or C API operations.
[Memory-safety testing](../../../docs/memory-safety-testing.md) gives the
exact conditions.

Release tests passed on Python 3.9, 3.12 and 3.13, with optional-reference and
interpreter-specific skips on 3.9. The upstream compatibility
suite passed 1,626 tests, with the same six skips as the reference and four
package-identity exclusions. Both Python 3.12 and 3.13 passed 56 native
binding tests. Miri checked the Rust parser and pointer-helper models;
AddressSanitizer checked the extension on all three Python versions.
[Validation counts and exclusions](PERFORMANCE_24H_REPRODUCTION.md#validation-results-and-entry-points)
are recorded separately from benchmark results.

Miri does not execute CPython. AddressSanitizer does not instrument the
installed interpreter or every native dependency, and leak detection was
disabled. Tests, allocation-failure checks and instruction review do not
prove memory safety or establish that jsonmodem is more secure than orjson.

## Commands and complete results

The measurements used Linux x86_64 on an AMD EPYC 7763, CPython 3.12.13,
Rust 1.94.1, thin LTO and one codegen unit. No profile-guided compilation or
`target-cpu=native` flag was used. Timings ran sequentially on one logical
CPU with its sibling unused by this task. This task's builds, tests and
profilers were stopped during timing; the host itself was not exclusive.

- [Reproduction commands and measurement limits](PERFORMANCE_24H_REPRODUCTION.md).
- [All suite means and build identities](data/final-2026-08-31/PERFORMANCE_FINAL.md).
- [All public-document cases](data/final-2026-08-31/PUBLIC.md).
- Maintained cases: [Original comparison](data/final-2026-08-31/MAINTAINED_ORIGINAL.md), [Rebuilt comparison](data/final-2026-08-31/MAINTAINED_REBUILT.md).
- Date/time: [Original comparison](data/final-2026-08-31/DATES_ORIGINAL.md), [Rebuilt comparison](data/final-2026-08-31/DATES_REBUILT.md).
- NumPy: [Original comparison](data/final-2026-08-31/NUMPY_ORIGINAL.md), [Rebuilt comparison](data/final-2026-08-31/NUMPY_REBUILT.md).
- [Malformed inputs](data/final-2026-08-31/MALFORMED.md).
- Memory: [public documents](data/final-2026-08-31/MEMORY_PUBLIC.md), [synthetic cases](data/final-2026-08-31/MEMORY_SYNTHETIC.md), [date/time](data/final-2026-08-31/MEMORY_DATES.md), [NumPy](data/final-2026-08-31/MEMORY_NUMPY.md).
- Incremental APIs: [Original comparison](data/final-2026-08-31/INCREMENTAL_ORIGINAL.md), [Rebuilt comparison](data/final-2026-08-31/INCREMENTAL_REBUILT.md).
- [Machine-readable observations](data/final-2026-08-31/data.json).
