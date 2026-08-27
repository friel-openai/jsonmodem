# Python decoding performance

This follow-up changes complete-document decoding. jsonmodem still provides
incremental parsing; the streaming API is unchanged and is measured separately
below. orjson does not provide an incremental parser.

The 171-case score improves from 1.34x to 1.31x orjson's time, a 2.25% reduction.
Long Unicode inputs take 38-51% less time; the 10,000-float case takes about
10% less. Encoding's score worsens by 0.57%, and some short-input and dataclass
cases regress by 8-12%. One short-string streaming case is 6.5% slower.
These costs are shown below. This is not a faster replacement for orjson on
every input.

## Changes

- `DocumentReader` still checks number grammar and preserves in-range integers.
  The Python frontend uses `lexical-parse-float` to convert validated decimal
  tokens to floating-point values. Overflow still raises a decoding error.
- Byte input of at least 128 bytes uses `simdutf8` for UTF-8 validation when
  the first 32 bytes contain non-ASCII text. Other input keeps Rust's standard
  validator. Valid input is borrowed; invalid input is rejected before a
  Python string is created. This does not strip a byte-order mark or replace
  malformed text.
- Unicode escapes use a checked four-byte lookup instead of four separate
  digit conversions. Incomplete or malformed escapes use the original scalar
  implementation, preserving its error and cursor position.

The changes add no `unsafe` block to jsonmodem. The new dependencies contain
unsafe implementations internally. Existing Python FFI and ownership checks
remain in use; this is not a claim that the extension or its dependencies are
free of unsafe code.

The SIMD dependency is pinned to
[`1890235`](https://github.com/rusticstuff/simdutf8/commit/1890235e87c59a44d45efa6a44fcf9b7166183d4),
an upstream fix that is not yet in a published release. The published 0.1.5
release failed an AVX2 Miri test: a prefetch expression formed an out-of-bounds
pointer. The pinned revision fixes that arithmetic. Building the Python
extension fetches this Git revision; it must not be replaced with the registry
release without checking that the fix is included.

The new `jsonmodem-py-validation` test crate shares the Python binding's exact
dependency pin. CI checks allocation ends, every alignment within a 64-byte
block, malformed sequences and Unicode boundaries under SSE4.2, AVX2 and
AVX-512 Miri configurations. These tests do not link Python. AddressSanitizer
separately checks the Python extension.

## Measurement method

The reference is PR #2 at
[`a44e49c`](https://github.com/friel-openai/jsonmodem/commit/a44e49c154987ee861ba65b2b889ddc1c5e76cdb).
Its runtime is unchanged from the [previous report](PERFORMANCE.md).
The measured update is
[`16ebeba`](https://github.com/friel-openai/jsonmodem/commit/16ebeba5d7b8e834dc0772f2b7df9c4d9aff6eec),
called "This PR" in the tables. The saved results identify both extension
SHA-256 hashes. Documentation and benchmark-report changes do not change the
measured runtime.

[Raw results](data/performance-followup/final) include every case and process
sample. [geomean.json](data/performance-followup/final/geomean.json) records the
exact aggregate scores and case counts.

Timing uses CPU 0 on a shared AMD EPYC 7763 host, CPython 3.12.13,
Rust 1.94.1, PyO3 0.25.1, orjson 3.11.9, NumPy 2.5.2 and jiter 0.16.0.
Release builds use thin LTO and one code-generation unit, without a native CPU
target flag. No task-owned builds, tests or profilers overlap timing.

Each complete-document case runs seven times for each jsonmodem build, in
fresh Python processes. Build order alternates; hash seeds are 1729 through
1735. Each process compares its jsonmodem build with orjson, checks equal
results, then measures three batches per library in alternating order. Both
libraries use the same call count, calibrated until the slower batch takes at least
0.04 seconds. Garbage collection is disabled during timing. Input construction
and process startup are excluded. Reported times are medians within each
process, then medians across processes.

`bench_output_buffers.py` and `bench_frontend.py` use the same keyword-argument
wrapper for both libraries. `bench_numbers.py` and `bench_strings.py` call
functions directly. That difference matters for tiny inputs: do not compare
absolute times across those two calling methods.

Per-case tables show absolute times. orjson times come from the processes
running the new jsonmodem build. Bold marks the lowest displayed value
in each row, including ties. Small differences do not establish a repeatable
lead. These results describe this host and these inputs, not all applications
or Python versions.

## Complete-document results

### Geometric mean

All 171 primary cases have equal weight: 28 output cases, 58 frontend cases,
25 number cases and 60 string cases. Input-type variants count separately;
some payloads occur in more than one script. Streaming, diagnostic repeats
and rejected experiments are excluded.

For each case, the scripts save the median of paired jsonmodem/orjson time
ratios. The score is `exp(mean(log(case_ratio)))`. It is not the ratio of
separately averaged times, nor an estimate for a particular application's
workload mix. The report defines no statistical confidence interval.

Time relative to orjson (lower is better). **1.00x is orjson's time**;
1.31x means 31% more time. This is the only ratio table:

| Cases | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| All 171 cases | 1.34x | 1.31x | **1.00x** |
| Decoding: 106 cases | 1.26x | 1.21x | **1.00x** |
| Encoding: 65 cases | 1.48x | 1.49x | **1.00x** |

The new build's median paired ratio is below orjson in 40 cases, versus 41 for
PR #2. Its overall score improves because the geometric mean also accounts
for how far apart the results are. A count of wins does not measure that
difference.
The [previous report](PERFORMANCE.md#overall-geometric-mean) retains the
separate PR #1 versus PR #2 comparison.

### Float and Unicode decoding

These cases use [bench_frontend.py](bench_frontend.py), including its common
Python call wrapper. The Unicode strings have about 128 KiB of UTF-8 data.
The escaped-string array contains 1,000 strings, each represented by three
`\uXXXX` escapes in the JSON input.

Time in microseconds per document (lower is better):

| Input | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| 10,000 floats | 548.546 | 489.983 | **276.695** |
| Two-byte Unicode string | 162.229 | 99.375 | **94.631** |
| Three-byte Unicode string | 199.759 | 98.380 | **83.230** |
| Four-byte Unicode string | 140.650 | 87.452 | **66.846** |
| 1,000 strings with Unicode escapes | 160.684 | 154.226 | **46.333** |

These additional cases use direct calls in
[bench_numbers.py](bench_numbers.py). Integer tokens outside the supported
64-bit range retain orjson's floating-point conversion behavior.

Time in microseconds per document (lower is better):

| Input | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| Long decimal fractions | 886.849 | 756.298 | **440.120** |
| Integer tokens larger than 64 bits | 1,169.691 | 951.589 | **662.649** |
| Floats from random bit patterns | 762.223 | 727.475 | **429.674** |

### Regressions

The following tables contain all 19 complete-document cases whose median
paired time increased by more than 3%. Twelve were slower in all seven process
pairs. They remain in the aggregate; no faster repeat replaces any result.

Encoding through the output wrapper, in microseconds per document
(lower is better):

| Operation and input | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| Upper-range unsigned integers | **277.323** | 285.411 | 334.132 |
| Integer dictionary keys | **35.230** | 37.614 | 35.493 |
| Nested dataclasses | 523.726 | 577.768 | **205.845** |
| Dataclasses with sorted dictionaries | 578.375 | 627.048 | **227.059** |
| Dataclasses with default callbacks | 272.040 | 292.572 | **133.713** |

Calls through the frontend wrapper, in microseconds per document
(lower is better):

| Operation and input | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| Decode small object: memoryview | 0.685 | 0.712 | **0.528** |
| Encode string with dense escapes | 216.319 | 231.232 | **189.522** |

Direct calls in the number benchmark, in microseconds per document
(lower is better):

| Operation and input | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| Decode small object | 0.322 | 0.347 | **0.274** |
| Decode one integer | **0.081** | 0.086 | 0.117 |
| Encode small object | 0.194 | 0.207 | **0.131** |

Direct string calls, in microseconds per document (lower is better):

| Operation and input | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| Decode short plain string: bytes | **0.088** | 0.093 | 0.128 |
| Encode short plain string | **0.077** | 0.080 | 0.086 |
| Decode short escaped string: bytes | **0.129** | 0.148 | 0.133 |
| Decode short escaped string: bytearray | 0.149 | 0.160 | **0.140** |
| Decode short escaped string: memoryview (bytes) | 0.206 | 0.225 | **0.139** |
| Decode short escaped string: memoryview (array) | 0.201 | 0.227 | **0.137** |
| Encode escaped values | 33.225 | 34.687 | **23.420** |
| Encode Unicode strings | 21.499 | 22.876 | **11.278** |
| Encode dictionary with unique keys | 34.243 | 36.082 | **12.090** |

Encoder source is unchanged in the retained build. Its regressions remain
unexplained; changed native function addresses are not proof of a cause.
These results justify the decoding changes for the measured numeric and
Unicode inputs, not a claim that all workloads improve.

## Streaming controls

The incremental API is unchanged. Numeric controls contain 1,024 values and
use chunks ending at complete tokens, targeting 512 bytes per chunk. Default
events use `JsonModem()`; byte-view events use `JsonModem(byte_views=True)`.
Event timings are not compared with orjson or jiter because they perform
different work.

Default number events, time for the entire stream in microseconds
(lower is better):

| Number input | PR #2 | This PR |
| --- | ---: | ---: |
| Small integers | **286.761** | 294.732 |
| Full-width signed integers | 369.218 | **360.402** |
| Upper-range unsigned integers | 378.832 | **372.864** |
| Floats | 381.349 | **374.871** |
| Mixed numeric types | 389.517 | **386.567** |
| 200-bit integers | **682.524** | 685.920 |

Byte-view number events, time for the entire stream in microseconds
(lower is better):

| Number input | PR #2 | This PR |
| --- | ---: | ---: |
| Small integers | 346.341 | **345.705** |
| Full-width signed integers | 428.412 | **418.518** |
| Upper-range unsigned integers | 426.152 | **418.187** |
| Floats | **447.634** | 447.735 |
| Mixed numeric types | **446.155** | 448.374 |
| 200-bit integers | **722.987** | 729.127 |

For the next table, both libraries materialize the complete array prefix
after every chunk. jsonmodem uses `JsonModemValues.view().snapshot()`; jiter parses
the accumulated prefix. jiter's time includes constructing contiguous input
bytes. The benchmark checks prefix equality before timing.

Time for all cumulative snapshots, in microseconds (lower is better):

| Number input | PR #2 | This PR | jiter |
| --- | ---: | ---: | ---: |
| Small integers | 426.889 | 433.191 | **251.778** |
| Full-width signed integers | 1,839.923 | **1,834.608** | 3,305.866 |
| Upper-range unsigned integers | 2,123.233 | **2,098.634** | 3,853.914 |
| Floats | 1,258.575 | 1,250.375 | **1,134.130** |
| Mixed numeric types | **1,608.274** | 1,626.586 | 2,256.651 |
| 200-bit integers | 17,310.782 | **17,252.248** | 18,146.088 |

String streams contain 1,024 strings. Four-byte strings use 512-byte chunks;
256-byte strings use 4,096-byte chunks. Each build runs in seven fresh
processes, measuring three batches of 200 streams per process. The exporter
case supplies read-only buffers through Python's buffer protocol.

Time for the entire string stream, in microseconds (lower is better):

| Strings and input mode | PR #2 | This PR |
| --- | ---: | ---: |
| 4-byte strings: default events | **299.395** | 318.849 |
| 4-byte strings: byte-view events | **468.723** | 470.355 |
| 4-byte strings: exporter with byte-view events | **483.664** | 485.264 |
| 256-byte strings: default events | **403.157** | 414.821 |
| 256-byte strings: byte-view events | 619.189 | **612.888** |
| 256-byte strings: exporter with byte-view events | 684.329 | **675.049** |

The short-string default-event case takes 6.5% more time, with six of seven
pairs slower. No other streaming median regresses by more than 3%. Event
counts and tracked string-stream allocations are unchanged. The saved files
retain all streaming results; streaming is excluded from the 171-case score.

## Profiling

Native profiles identified UTF-8 validation and decimal conversion as costs
worth measuring separately. Profiles used py-spy 0.4.2; wall-clock benchmarks
ran without a profiler. Source-qualified Rust samples support the selected
functions as optimization targets. CPython symbol attribution was unreliable,
so no CPython function percentages are reported. Inclusive stack samples are
not measurements of time spent exclusively in one function.

The final Unicode profile contains 391 sampled stacks from the measured
loop; 39 include the SIMD validator. The standard-validator profile contains
151 validator stacks among 389 loop samples. Each capture lasts eight seconds
at 49 samples per second, on CPU 6 for the new build and CPU 8 for the reference.
These counts support the validation work as an
optimization target; the timing tables measure the actual change.

## Memory

Memray 1.20.0 records Python and native allocations on CPU 12 after input construction,
ten warmup calls and garbage collection. Allocation measurements use 30 calls
with garbage collection disabled. Total allocated bytes include temporary
storage that is freed during those calls. Peak live bytes are the largest
simultaneously tracked allocation total. Neither measure is process RSS.

Allocation requests over 30 calls (lower is better):

| Input per call | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| 10,000 floats | 298,506 | 298,506 | **297,156** |
| 128 KiB Unicode string | 98 | 98 | **68** |
| 1,000 strings with Unicode escapes | 120,878 | 120,878 | **30,068** |
| 8 MiB invalid UTF-8 input | 490 | 490 | **430** |

Total allocated memory over 30 calls, in MiB (lower is better):

| Input per call | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| 10,000 floats | **28.264** | **28.264** | 66.511 |
| 128 KiB Unicode string | **13.755** | **13.755** | 47.619 |
| 1,000 strings with Unicode escapes | 9.880 | 9.880 | **9.792** |
| 8 MiB invalid UTF-8 input | 0.041 | 0.041 | **0.039** |

Peak live tracked memory during 30 calls, in KiB (lower is better):

| Input per call | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| 10,000 floats | **317.8** | **317.8** | 2,272.8 |
| 128 KiB Unicode string | **384.4** | **384.4** | 1,625.7 |
| 1,000 strings with Unicode escapes | **75.5** | **75.5** | 334.5 |
| 8 MiB invalid UTF-8 input | 2.8 | 2.9 | **1.3** |

This change does not reduce allocation counts or total allocated bytes. The
invalid-input peak is 56 bytes higher; the other three peaks are unchanged.
jsonmodem makes more allocation requests than orjson in all four cases, but
has a smaller tracked peak for the three valid inputs.

Process RSS is measured separately on CPU 12 by `bench_rss.py`, without Memray. Each
library runs in five fresh processes per case and makes ten calls per process.
Inputs are prepared before the calls; decoded input fixtures are generated in
a separate process. The results retain both pre-call RSS and the whole-process
peak. Imports, input storage, allocator retention and interpreter overhead are
included in process RSS.

Median whole-process peak RSS, in MiB (lower is better):

| Workload | PR #2 | This PR | orjson |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | 18.76 | 18.72 | **18.00** |
| Decode 100,000 records | 55.50 | **55.45** | 73.40 |
| Encode mixed records | 18.89 | 18.81 | **17.69** |
| Encode 1,000 fragments | 17.57 | 17.61 | **17.22** |
| Encode 1,000 dataclasses | 18.52 | 18.54 | **17.70** |
| Encode NumPy float32 | **35.43** | 35.52 | 36.02 |
| Default callback after 100 strings | 59.41 | 59.62 | **38.66** |

The jsonmodem RSS medians differ by less than 0.5% between builds. This is not
a statistical equivalence test. The orjson column uses the new build's control
runs; both sets of controls remain in the saved data. The late-callback case
still uses more process memory than orjson.

## Rejected experiments

The following implementations were tested and removed:

- Combining number grammar and conversion improved long fractions, but slowed
  ordinary float arrays and single integers compared with the smaller
  converter change.
- Reusing sorted-dictionary storage reduced allocation requests for repeated
  small dictionaries. It also slowed ordinary escaped output and dataclasses
  with sorted dictionaries. The dedicated
  [sorted-storage benchmark](bench_sorted_storage.py) remains available.
- Direct output allocation for short root strings removed temporary buffers,
  but slowed short escaped strings and mixed-record output.
- Preallocating Python lists exposed incomplete list entries to a Python
  callback. The retained decoder appends fully constructed values instead.
- Passing plain root strings directly to CPython's UTF-8 decoder improved
  valid Unicode input, but allocated large temporary storage before rejecting
  malformed input. Validation still precedes Python string construction.
- Key-cache, dataclass-snapshot and numeric-prefix changes did not improve
  their controls consistently enough to retain.

The earlier complete-suite run with `encoding_rs` and its diagnostic repeats
remain in [the initial measurements](data/performance-followup/initial).
They are not substituted for any final result.

## Checks

Before publication, the measured runtime passed:

- 1,182 Python binding tests and 71 benchmark fixture tests.
- 1,626 tests from orjson 3.11.9's release suite, with six skips and four
  package-identity exclusions.
- Core Rust tests, formatting, Clippy, documentation and workflow syntax checks.
- Four UTF-8 dependency tests under each of SSE4.2, AVX2 and AVX-512 Miri.
  Separate decimal-conversion and Unicode-escape Miri checks also passed.
- Rust 1.85.1 checks for the Python crate and the UTF-8 dependency tests.
- Python 3.9 AddressSanitizer: 796 passed, 120 skipped. Python 3.13
  AddressSanitizer: 1,179 passed, three skipped.

The sanitizer runs first verify that an intentional invalid read is detected.
Leak detection is disabled; these runs check invalid memory accesses. Python
3.9 uses NumPy 2.0.2 and skips comparisons requiring orjson 3.11.9, which requires
Python 3.10 or newer. Python 3.13 uses NumPy 2.5.2 and orjson 3.11.9; its three
skips are address-space-limit tests incompatible with the sanitizer.

## Remaining opportunities

`decode_bytes()` still selects SIMD only when a long input has non-ASCII text
in its first 32 bytes. Testing a wider selection could help Unicode that
appears later in a document. ASCII, short inputs and malformed text must remain
controls; the current measurements do not establish a better threshold.

PyO3's ordinary tuple iterator creates an owned reference for every item.
Borrowing initial scalar items while retaining the tuple may avoid those
reference-count changes. An owning iterator must take over before callbacks;
repeatedly skipping a borrowed prefix could instead make iteration slower.
This idea has not been implemented or timed.

Python string construction still decodes validated UTF-8 again. The public
`PyUnicode_FromKindAndData` constructor can copy initialized Unicode code-point
buffers, but it still scans and copies them. UTF-16 surrogate pairs cannot be
passed as separate Python characters. The extra conversion, allocation and
validation requirements need a separate measured experiment.

## Reproduce

Use the [build and benchmark instructions](PERFORMANCE.md#reproduce) with
the two revisions named above and the listed dependency versions. Run all
cases in `bench_output_buffers.py`, `bench_frontend.py`, `bench_numbers.py`
and `bench_strings.py`, with seven process comparisons and 0.04-second batches.
For the string script, include both operations and all four input types:

```bash
taskset -c 0 python crates/jsonmodem-py/benchmarks/bench_strings.py \
  --baseline-package "$BASELINE" --candidate-package "$CANDIDATE" \
  --pairs 7 --seconds 0.04 --operations loads dumps \
  --inputs bytes bytearray memoryview array_view --output strings.json
```

Run the streaming commands separately; they do not contribute to the score.
For Memray, use `profile_compat.py` with `--calls 30 --mode memray` and each
of `loads_floats`, `loads_bmp`, `loads_unicode_escapes` and
`loads_invalid_utf8`. Run all four with PR #2, this build and `--module orjson`,
using a new output filename each time. Run `bench_rss.py --runs 5 --calls 10`
with each jsonmodem build; it also measures orjson. Save its JSON with
`--output`. Do not overlap timing with these allocation or RSS measurements.
