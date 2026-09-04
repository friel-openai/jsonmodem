# Optional fixed-timezone cache

The Python encoder now reuses checked offsets for repeated, exact built-in
timezone objects within one `dumps()` call. The cache owns at most eight
timezone references, skips root datetimes, and stops searching after sixteen
consecutive misses. It adds no handwritten unsafe code. The Rust parser and
incremental APIs are unchanged.

Keep this cache, with the default-enabled `python-acceleration` Cargo feature
and the per-call `jsonmodem.portable.dumps` alternative. The main benefit is
encoding many dates with a few shared fixed timezones. Short calls with many
distinct timezones can become slower. The broader suite improves only slightly,
and several unrelated cases regress. This change does not make jsonmodem faster
than orjson overall.

## Complete-call reference results

Microseconds per call; **lower is better**. Each suite gives every case equal
weight in a geometric mean. The overall row weights all 275 cases equally,
rather than weighting each suite equally. Bold marks the lowest measured value.

| Suite | PR #7 | Timezone cache | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| All 275 comparable cases | 76.275 | 75.151 | **54.897** |
| Output | 107.213 | 107.413 | **59.423** |
| Frontend | 39.039 | 38.134 | **27.445** |
| Numbers | 66.923 | 66.510 | **53.464** |
| Strings | 47.516 | 47.043 | **33.311** |
| Dates | 27.108 | 26.258 | **19.930** |
| NumPy | 27.684 | **27.616** | 32.801 |
| Public documents | 2,881.350 | 2,827.517 | **1,699.712** |

The cache takes 1.5% less time than PR #7 and 36.9% more time than measured
orjson. Comparing each process with its paired orjson control reduces the
apparent improvement to 0.03%, 0.65%, and 1.60% in the three process orders.
These measurements support a small aggregate improvement, not a precise
universal speedup. orjson 3.12.0 was not measured.

## Where the cache helps and hurts

Microseconds per call; **lower is better**. These supplemental cases are not
included in the 275-case mean. A timezone owner is one distinct Python timezone
object. Portable means the same feature-enabled package with caching disabled
for that call.

| Input | PR #7 | Timezone cache | Portable | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: |
| 1,024 dates, one timezone owner | 135.731 | **96.322** | 139.398 | 172.838 |
| 1,024 dates, two owners | 135.223 | **95.711** | 142.058 | 172.522 |
| 1,024 dates, eight owners | 135.250 | **99.788** | 139.495 | 170.885 |
| 1,024 dates, nine owners | **133.953** | 140.407 | 137.273 | 169.290 |
| 1,024 dates, 64 owners | **136.195** | 139.902 | 139.299 | 174.404 |
| 16 dates, one owner | 3.570 | **3.033** | 3.710 | 3.077 |
| 16 dates, nine owners | 3.533 | 4.400 | 3.628 | **3.013** |
| 16 dates, all distinct owners | 3.517 | 4.492 | 3.626 | **3.145** |
| Root datetime | 1.056 | 1.072 | 1.082 | **0.470** |
| One date in a list | 1.207 | 1.293 | 1.378 | **0.486** |
| Large integer list | 202.101 | 213.390 | 210.653 | **72.237** |
| Tiny dictionary | 0.383 | 0.395 | 0.397 | **0.350** |
| 513-byte output | 0.598 | 0.641 | 0.609 | **0.433** |

For 1,024 dates sharing one timezone, time falls by 29.0% from PR #7. The
sixteen-miss limit reduces the initial cache's nine-owner result from 183.516
to 140.407 us and its 64-owner result from 197.985 to 139.902 us. It cannot
recover its setup cost in the short miss cases: 16 dates with distinct owners
take 27.7% longer than PR #7. The cache remains bounded and optional, but it
does not improve every date workload. The last miss fixture is named
`offsets_64_owners_16_dates` because its generator prepares 64 timezone objects;
only the first sixteen are present in the encoded list.

Some wider regressions are larger than the overall gain. Microseconds per call;
**lower is better**.

| Input | PR #7 | Timezone cache | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Encode `otfcc` | 1,146,353.897 | 1,289,737.844 | **559,434.420** |
| Decode Unicode escapes from bytes | 290.440 | 318.544 | **81.491** |
| Encode plain string values | 41.876 | 45.895 | **12.359** |
| Encode sixteen-field dataclasses | 1,163.626 | 1,253.626 | **497.078** |

`otfcc` encoding regresses in all three process orders, by 8.9% to 13.6%.
The cause is unresolved. A fixed-timezone cache cannot directly explain a
Unicode decoding change, and these results do not establish a compiler or
code-layout explanation. The complete observations retain these losses.

## Incremental parsing

The 45 streaming cases cover events, minimal events, tracked events, values,
and prefix snapshots, with records, numbers, and Unicode at three chunk sizes.
All compared outputs match. Microseconds per operation; **lower is better**.

| Measurement | PR #7 | Timezone cache |
| --- | ---: | ---: |
| Equal-case geometric mean | 605.306 | **604.744** |
| Tracked record events, 64-byte chunks | **670.900** | 725.535 |
| Numeric prefix snapshots, 256-byte chunks | **925.592** | 1,001.326 |

The aggregate is effectively unchanged, with individual losses of 8.1% and
8.2% in the two rows shown. No incremental-parser speedup is claimed. orjson
has no corresponding incremental event API, so it is not in this table.

## Allocations

Memray 1.20.0 recorded 30 calls after ten warmup calls, discarding each result.
Python allocator tracing was enabled; native stack tracing was disabled.
Each fixture has one capture per implementation. These are allocation counts,
not latency shares. PR #7, the selected cache, and portable mode had identical
counts and byte totals in all seven fixtures. The refinement removes the
initial cache's extra root-datetime allocations.

Allocation requests across 30 calls; **lower is better**.

| Input | PR #7 | Timezone cache | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| 1,024 dates, one owner | **427** | **427** | 30,997 |
| 1,024 dates, 64 owners | **427** | **427** | 30,997 |
| Root datetime | 157 | 157 | **127** |
| Tiny dictionary | 127 | 127 | **97** |
| 513-byte output | 187 | 187 | **127** |
| Large integer list | 367 | 367 | **277** |
| Late `default` callback | 398 | 398 | **218** |

Total allocated KiB across 30 calls; **lower is better**. One KiB is 1,024 bytes.

| Input | PR #7 | Timezone cache | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| 1,024 dates, one owner | **5,134.9** | **5,134.9** | 5,978.96 |
| 1,024 dates, 64 owners | **5,134.9** | **5,134.9** | 5,978.96 |
| Root datetime | **13.12** | **13.12** | 35.27 |
| Tiny dictionary | **11.13** | **11.13** | 33.16 |
| 513-byte output | **70.69** | **70.69** | 274.13 |
| Large integer list | 5,382.07 | 5,382.07 | **3,818.96** |
| Late `default` callback | **204.41** | **204.41** | 522.64 |

Peak live KiB during those calls; **lower is better**.

| Input | PR #7 | Timezone cache | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| 1,024 dates, one owner | 72.07 | 72.07 | **64.14** |
| 1,024 dates, 64 owners | 72.07 | 72.07 | **64.14** |
| Root datetime | **0.35** | **0.35** | 1.14 |
| Tiny dictionary | **0.34** | **0.34** | 1.10 |
| 513-byte output | **1.57** | **1.57** | 8.10 |
| Large integer list | 115.62 | 115.62 | **64.10** |
| Late `default` callback | **5.90** | **5.90** | 19.82 |

## Process memory

RSS is measured separately, without Memray or warmup, with 30 results retained.
Each implementation uses a fresh process. Imports and fixture preparation are
outside the calls but included in process memory. These values do not isolate
serializer memory or the cache's eight references. One MiB is 1,048,576 bytes;
**lower is better**.

| Input | PR #7 RSS, MiB | Timezone cache RSS, MiB | orjson 3.11.9 RSS, MiB |
| --- | ---: | ---: | ---: |
| 1,024 dates, one owner | 21.219 | 21.234 | **20.574** |
| 1,024 dates, 64 owners | 21.238 | 21.242 | **20.543** |
| Root datetime | 20.406 | 20.320 | **19.520** |
| Tiny dictionary | 20.406 | 20.328 | **19.438** |
| 513-byte output | 20.414 | 20.312 | **19.453** |
| Large integer list | 21.844 | 21.766 | **21.008** |
| Late `default` callback | 20.418 | 20.266 | **19.547** |

orjson has lower RSS in all seven cases despite making more allocation requests
for the date lists. Allocation count, total allocated bytes, peak live bytes,
and process RSS measure different costs.

## Method and complete results

Measurements used Linux x86_64, CPython 3.12.13, Rust 1.94.1, and orjson 3.11.9.
Timing ran on one pinned CPU without concurrent builds, profiling, or transfers.
The base is commit `70638485a81064da41167163681c5fcde265f4bc` from PR #7.
The selected extension's SHA-256 is
`4236eb18f08298758560766b4a9bf597f7cdeaaeea3f9001700c1fa5620b773b`.

Three fresh-process comparisons rotated package order: base/initial/selected,
selected/initial/base, and initial/base/selected. Each process measured its
paired orjson control. Tables use the median for each case across the three
processes; the orjson column uses the median of all corresponding controls.
Calibration targeted 0.03 seconds. Three existing unequal-output date cases
(`time_16`, `time_1024`, `dates_under_dict`) remain excluded from the overall
mean and are retained in the observations. This change does not close those
compatibility differences.

The supplemental fixtures are in [bench_acceleration.py](bench_acceleration.py).
The maintained suites use `bench_output_buffers.py`, `bench_frontend.py`,
`bench_numbers.py`, `bench_strings.py`, `bench_datetime.py`,
`bench_numpy_dates.py`, and `bench_public_corpus.py`.

The CSV identifiers are `base` for PR #7, `cache1` for the initial cache,
`cache2` for the selected cache, and `portable` for selected calls without caching.
All times are absolute microseconds; all memory columns state their units.

- [All complete-call and supplemental medians](python_acceleration_timings.csv)
- [Every complete-call observation and paired control](python_acceleration_observations.csv)
- [All incremental medians](python_acceleration_streaming.csv)
- [Allocation counts and bytes](python_acceleration_allocations.csv)
- [RSS and high-water observations before and after calls](python_acceleration_rss.csv)

A separate inline-buffer experiment was rejected. In its own paired comparison,
the 275-case mean was 78.644 us versus 75.505 us for PR #7 and 54.698 us for
orjson. Fewer allocations did not compensate for its 4.2% overall time loss.
Those results must not be combined with the selected-cache comparison.

See [the validation record](../../../plans/python-acceleration/record.md) for
native tests, Miri coverage, sanitizer results, and their limits.
