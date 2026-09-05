# Checked Python arguments and shared string scanning

Keep the checked text conversions, owning keyword-argument snapshots, and
bounded string classifier. Complete-call and incremental performance are
essentially unchanged from PR #8. Some long-string decoding improves, but
two root-string encoding cases regress about 28%. This change does not make
JSONModem faster than upstream orjson overall.

The classifier reads exactly sixteen initialized bytes through a safe Rust
interface. Its SSE2 implementation is selected by the default-enabled `simd`
feature, independently of `cached-zipper`. Disabling both forbids unsafe code
in the core crate, not in its dependencies or Python binding. The existing
`jsonmodem.portable.dumps()` alternative disables Python encoder acceleration
for a call; it does not disable the core SIMD classifier or decoder.

The PyO3 fixes are required in every configuration. Keyword names and values
stay owned through argument conversion, the Rust call and return conversion.
Python-produced UTF-8 is checked before it becomes a Rust string. See
[CPython adapters](../../../docs/cpython-adapters.md) for invariants, supported
versions, public-library comparisons, and limitations.

## Complete-call reference results

Microseconds per call; **lower is better**. Bold marks the lowest value.
Each case has equal weight in its suite's geometric mean. The overall mean
weights all 275 cases equally, rather than weighting suites equally.

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

Hardened takes 0.3% more time than PR #8 and 31.9% more than orjson.
Adjusting each process by its paired orjson control gives changes of -0.40%,
+0.03%, and +0.02% from PR #8. These measurements do not establish a repeatable
aggregate speedup. Upstream orjson 3.12.0 was not measured.

## Gains and regressions

Microseconds per call; **lower is better**. The first five changes occur in
the same direction in all three fresh-process comparisons. The complete CSV
retains every case, including regressions not shown here.

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

BMP means Unicode's Basic Multilingual Plane, through U+FFFF. The final
comparison combines required text and argument-lifetime fixes with shared
classification. It does not isolate each change's latency cost. A function
appearing in the source does not establish its share of these regressions.

Two separate experiments were rejected. Owning numeric specialization increased
the 275-case mean from 57.430 to 58.230 us and regressed integer output in all
three comparisons. Eight-escape batching made dense escaped-string decoding
56-62% slower than its immediate parent. Their implementations were removed;
the numeric correctness cases and parser content/error tests remain. Neither
experiment is counted as a shipped gain.

## Incremental parsing

The 45 fixtures cover records, numbers and Unicode with 16-, 64- and 256-byte
chunks. All event/value traces match. Microseconds per operation;
**lower is better**.

| Operation | PR #8 | Hardened |
| --- | ---: | ---: |
| All 45 cases | **492.106** | 492.540 |
| Events | **333.551** | 334.196 |
| Minimal events | 252.562 | **252.443** |
| Tracked events | **334.600** | 334.957 |
| Values | 468.339 | **464.586** |
| Prefix snapshots | **2,186.119** | 2,207.944 |

The 0.09% aggregate increase is smaller than variation between process orders.
The largest per-case median regression is numeric prefix snapshots with 16-byte
chunks: 4,976.763 to 5,209.799 us, or 4.7% more time. Unicode events with
16-byte chunks improve from 298.439 to 285.754 us, or 4.3% less time.
No overall streaming speedup is claimed. orjson has no corresponding
incremental event API.

## Allocations

Memray 1.20.0 recorded thirty calls after ten warmup calls, discarding each
result. Python allocator tracing was enabled; native stack tracing was disabled.
Each fixture has one capture per implementation. PR #8, hardened, and portable
mode produced identical allocation counts and byte totals in all twelve
fixtures. The tables use one JSONModem column for those identical results.
These fixtures do not measure keyword-argument snapshot construction.

Allocation requests across thirty calls; **lower is better**.

| Input | JSONModem | orjson 3.11.9 |
| --- | ---: | ---: |
| Small dictionary | 127 | **97** |
| Integer list | 367 | **277** |
| Sixteen-field dataclasses | 30,607 | **337** |
| NumPy int64 output | **1,150** | 751,027 |
| Decode long plain string | **97** | 127 |
| Decode Unicode escapes | 120,967 | **30,127** |

Total allocated KiB across thirty calls; **lower is better**. One KiB is
1,024 bytes.

| Input | JSONModem | orjson 3.11.9 |
| --- | ---: | ---: |
| Small dictionary | **12.39** | 33.16 |
| Integer list | 5,382.07 | **3,818.96** |
| Sixteen-field dataclasses | 29,877.48 | **15,340.90** |
| NumPy int64 output | **101,743.48** | 226,745.56 |
| Decode long plain string | **3,843.40** | 50,043.40 |
| Decode Unicode escapes | 10,120.40 | **10,028.76** |

Peak live KiB during the calls; **lower is better**.

| Input | JSONModem | orjson 3.11.9 |
| --- | ---: | ---: |
| Small dictionary | **0.38** | 1.10 |
| Integer list | 115.62 | **64.10** |
| Sixteen-field dataclasses | 264.55 | **256.10** |
| NumPy int64 output | **2,433.88** | 3,978.38 |
| Decode long plain string | **128.11** | 1,668.08 |
| Decode Unicode escapes | **76.83** | 334.26 |

JSONModem has lower peak live allocation in nine of twelve fixtures. Integer
lists, sixteen-field dataclasses and late-default output have higher peaks.
Allocation counts, total allocated bytes and peak live bytes measure different
costs; none gives a function's share of runtime.

## Process memory

RSS was measured in separate processes without Memray or warmup, retaining
thirty results. Imports and fixture preparation are included. All processes
also import orjson to prepare and check the common fixtures. These measurements
do not isolate serializer memory or explain the timing changes.
MiB of RSS after the calls; **lower is better**. One MiB is 1,048,576 bytes.

| Input | PR #8 | Hardened | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Small dictionary | 41.020 | 41.039 | **39.809** |
| Integer list | 42.219 | 42.402 | **41.262** |
| Sixteen-field dataclasses | 47.664 | 47.793 | **47.535** |
| Late default callback | 41.496 | 41.504 | **41.375** |
| NumPy int64 output | **61.527** | 61.586 | 62.125 |
| Encode long plain string | 26.848 | **26.727** | 29.141 |
| Encode densely escaped string | 26.039 | **25.734** | 27.719 |
| Decode long plain string | 26.809 | **26.699** | 28.086 |
| Decode densely escaped string | 25.641 | 25.629 | **25.344** |
| Decode Unicode escapes | 27.516 | 27.445 | **27.293** |
| Decode repeated escaped keys | 31.340 | 31.379 | **31.316** |
| Decode floating-point values | 35.016 | 35.062 | **34.883** |

Hardened has higher RSS than orjson in eight of twelve fixtures, despite its
lower peak live allocations in most fixtures. Each RSS cell is one process
observation, not a confidence interval. Small differences should not be
treated as repeatable improvements.

## Method and complete results

Measurements used Linux x86_64, CPython 3.12.13, Rust 1.94.1 and orjson 3.11.9.
Timing used one pinned CPU without concurrent builds, profiling or transfers.
The base is PR #8 commit `c9ab60b4a6ecb28ed800f4e5f23953175c41613f`.
The hardened extension was built from its source distribution; its SHA-256 is
`0d4ed698ed92e1967219768d9e8720cbe2538b448cc4734effadfdf58a5d48d4`.

Complete-call comparisons used three fresh processes per implementation and
suite, alternating package order and changing the process hash seed. Each
process timed a paired orjson control. Tables use each case's median across
the processes; the orjson column pools its corresponding paired controls.
Calibration targeted 0.03 seconds. Three existing unequal-output date cases
(`time_16`, `time_1024`, `dates_under_dict`) remain excluded from the 275-case
mean and included in the observations. This change does not fix those output
differences. Streaming used the same three-comparison aggregation with
0.01-second calibration and three samples per process.

The maintained fixtures are in `bench_output_buffers.py`, `bench_frontend.py`,
`bench_numbers.py`, `bench_strings.py`, `bench_datetime.py`,
`bench_numpy_dates.py`, and `bench_public_corpus.py`. The public corpus is
documented in [PUBLIC_CORPUS.md](PUBLIC_CORPUS.md).

- [All 275 complete-call medians](hardened_timings.csv)
- [Every complete-call observation and paired control](hardened_observations.csv)
- [All 45 incremental medians](hardened_streaming.csv)
- [All twelve allocation fixtures and portable results](hardened_allocations.csv)
- [RSS and high-water observations before and after calls](hardened_rss.csv)

The CSV identifiers are `pr8`, `hardened`, `portable`, and `orjson`. Every
numeric column names its unit. See the [validation record](../../../plans/hardened-acceleration/record.md)
for native tests, actual-kernel Miri, sanitizers, archive builds and remaining
safety limits. None proves safety for every Python object or malformed native
buffer provider; free-threaded CPython remains unsupported.
