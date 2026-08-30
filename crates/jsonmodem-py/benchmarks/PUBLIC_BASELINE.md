# Public JSON benchmark baseline

This report compares the unchanged jsonmodem baseline at commit
`b7fe329765f3e90064cc38f127d3594165116c71` with **orjson 3.11.9**. It records a
starting point for further optimization, not a final optimized-build comparison.
All measurements are from 2026-08-29, using CPython 3.12.13 on Linux x86_64.
Recorded interpreter and library file hashes match across the measurements.
CPU model and clock settings are not in the recorded metadata.

The [18-document corpus](PUBLIC_CORPUS.md#documents-and-sources) was selected
before comparing the libraries. It includes public parser benchmarks with
numeric arrays, nested objects, long strings, Unicode, and different file sizes.
It is not a measured distribution of application traffic. These are complete
Python `loads()` and `dumps()` calls, not incremental parsing measurements.
Synthetic benchmarks are not included in these aggregates.

Tables show absolute measurements. **Bold marks the lower recorded median**,
not a statistical significance test. Times are milliseconds per call. Memory
uses MiB, where 1 MiB = 1,048,576 bytes. Full-precision values, repeated samples,
and fingerprints are available in the
[result data](data/public-baseline-2026-08-29/README.md).
The [additional memory report](PUBLIC_SUPPLEMENTAL_MEMORY.md) covers synthetic
workloads and first-use public-document allocations in separate measurements.

## Repeated-call timing

Each library ran in eight independent interpreter processes on CPU 12. Each
case had three timing samples, targeting 50 ms per sample, after three warmup
calls and calibration. Tables show the median of the eight process medians.
Library order was rotated; document order was shuffled deterministically.
The session also measured two experimental builds; this report selects only
unchanged jsonmodem and orjson, while original worker positions remain in the data.

`loads()` receives the original bytes and constructs complete Python values.
`dumps()` receives values prepared with standard-library `json.loads()`. Input
preparation, reads, hashes, and correctness checks are outside timing.
**Releasing each returned result is included in the timing.** Cyclic GC is
disabled during warmup, calibration, and timing. Repeated calls reuse the same
prepared input.
The workers also retain a correctness reference, so their process RSS is not a
decode-memory measurement.

Across the 18 documents, the geometric-mean jsonmodem/orjson latency ratio is
**1.510 for loads** and **2.227 for dumps**. Across all 36 document/operation
cases, it is **1.834**. For each case, divide jsonmodem's median latency by
orjson's median, then take the geometric mean with one equal weight per case.
A larger file does not receive more weight. Lower is better; 1 means equal
latency. This is not a ratio of total elapsed time or a traffic-weighted result.

jsonmodem has a lower median for `gsoc-2018` loads. orjson has a lower median in
the other 35 repeated-call cases.

### Repeated calls: loads

Lower is better.

| Document | jsonmodem baseline (ms) | orjson 3.11.9 (ms) |
| --- | ---: | ---: |
| apache_builds | 0.353 | **0.238** |
| canada | 8.600 | **5.880** |
| citm_catalog | 3.898 | **2.409** |
| github_events | 0.157 | **0.091** |
| google_maps_api_response | 0.080 | **0.051** |
| gsoc-2018 | **4.060** | 4.372 |
| instruments | 0.629 | **0.372** |
| marine_ik | 14.822 | **11.402** |
| mesh | 2.783 | **1.854** |
| numbers | 0.440 | **0.270** |
| random | 2.791 | **1.688** |
| semanticscholar-corpus | 34.541 | **30.921** |
| tree-pretty | 0.106 | **0.054** |
| twitter | 1.915 | **1.059** |
| twitterescaped | 2.029 | **1.113** |
| update-center | 2.110 | **1.415** |
| poet | 7.150 | **5.407** |
| otfcc | 1,125.413 | **749.012** |

### Repeated calls: dumps

Lower is better.

| Document | jsonmodem baseline (ms) | orjson 3.11.9 (ms) |
| --- | ---: | ---: |
| apache_builds | 0.162 | **0.069** |
| canada | 5.999 | **4.037** |
| citm_catalog | 1.761 | **0.602** |
| github_events | 0.067 | **0.025** |
| google_maps_api_response | 0.034 | **0.014** |
| gsoc-2018 | 1.550 | **0.810** |
| instruments | 0.310 | **0.115** |
| marine_ik | 8.317 | **5.022** |
| mesh | 1.876 | **1.302** |
| numbers | 0.409 | **0.301** |
| random | 0.937 | **0.423** |
| semanticscholar-corpus | 10.806 | **4.510** |
| tree-pretty | 0.047 | **0.016** |
| twitter | 0.776 | **0.302** |
| twitterescaped | 0.785 | **0.304** |
| update-center | 0.921 | **0.391** |
| poet | 2.117 | **0.987** |
| otfcc | 392.472 | **118.413** |

## First serialization and reused inputs

This separate measurement uses nine fresh interpreter processes for each
library, document, and input condition on CPU 8. Each process makes ten untimed
calls, then times one call. In the fresh condition, the worker releases the
warmup input before preparing a replacement with standard-library `json.loads()`.
In the reused condition, it keeps the warmup input. Only one parsed copy of the
document exists when timing starts, with no correctness reference retained.

The actual timed output is checked after the stopwatch stops.
**Releasing the returned bytes is excluded from the timing.** Tables show the
median of nine single-call latencies. Do not combine these results with the
repeated-call tables: input lifetime, process scheduling, CPU selection, and the timed
release of results differ. See [the method and runner](PUBLIC_FRESH_DUMPS.md).

The equal-document geometric-mean latency ratios are **2.067 for fresh input**
and **2.345 for reused input**. orjson has a lower median in all 18 documents in
both conditions. The smaller fresh-input ratio does not mean fresh inputs are
faster: for `poet`, both libraries take longer on fresh input. Allocator state,
processor caches, and interpreter-shared objects can also affect these results;
this comparison does not isolate UTF-8 caching as the cause.

### Single call: fresh input

Lower is better.

| Document | jsonmodem baseline (ms) | orjson 3.11.9 (ms) |
| --- | ---: | ---: |
| apache_builds | 0.149 | **0.058** |
| canada | 5.996 | **3.936** |
| citm_catalog | 1.678 | **0.543** |
| github_events | 0.077 | **0.029** |
| google_maps_api_response | 0.035 | **0.015** |
| gsoc-2018 | 1.984 | **1.162** |
| instruments | 0.290 | **0.107** |
| marine_ik | 8.680 | **4.878** |
| mesh | 2.112 | **1.518** |
| numbers | 0.393 | **0.292** |
| random | 1.026 | **0.581** |
| semanticscholar-corpus | 12.064 | **7.943** |
| tree-pretty | 0.048 | **0.017** |
| twitter | 0.875 | **0.393** |
| twitterescaped | 0.868 | **0.391** |
| update-center | 0.889 | **0.355** |
| poet | 4.698 | **3.609** |
| otfcc | 398.721 | **118.504** |

### Single call: reused input

Lower is better.

| Document | jsonmodem baseline (ms) | orjson 3.11.9 (ms) |
| --- | ---: | ---: |
| apache_builds | 0.144 | **0.056** |
| canada | 5.839 | **3.935** |
| citm_catalog | 1.656 | **0.518** |
| github_events | 0.063 | **0.023** |
| google_maps_api_response | 0.033 | **0.014** |
| gsoc-2018 | 1.445 | **0.670** |
| instruments | 0.284 | **0.102** |
| marine_ik | 8.200 | **4.857** |
| mesh | 1.848 | **1.268** |
| numbers | 0.393 | **0.293** |
| random | 0.853 | **0.347** |
| semanticscholar-corpus | 10.318 | **4.093** |
| tree-pretty | 0.045 | **0.016** |
| twitter | 0.715 | **0.261** |
| twitterescaped | 0.757 | **0.264** |
| update-center | 0.841 | **0.332** |
| poet | 1.914 | **0.834** |
| otfcc | 411.145 | **120.088** |

## Initial memory measurements

**These initial memory captures allowed concurrent builds and correctness
checks.** Individual overlapping jobs were not logged. Repeat the memory
comparison without competing heavy work before interpreting small differences,
especially RSS. The fresh/reused timing run above used a separate window with
other workers' heavy jobs paused.

Memory uses three independent processes per library, document, operation, and
metric, on CPU 8. The following tables show their medians. Memray 1.20.0 tracks
one call after ten warmups, with Python allocator tracing enabled. RSS is
measured in separate processes without Memray: ten calls, with no warmups.
Returned values are released before the next call in both measurements.

The metrics answer different questions:

- **Allocation requests** count allocating calls, including zero-byte requests.
  Deallocations are excluded even when their records have positive sizes.
- **Total allocated bytes** add the requested sizes, including each realloc's
  full new size. They are cumulative requests, not simultaneously live memory.
- **Tracked peak bytes** are Memray's maximum live bytes during the tracked
  call. Input preparation, warmup allocations, and preexisting allocations are
  excluded. This is not process RSS.
- **Whole-process peak RSS** is Linux's recorded peak resident memory. It
  includes the interpreter, imports, input preparation, results, temporary
  allocations, and retained allocator pages. Preparation can set the peak before
  a measured library call. Subtracting a starting RSS value does not isolate
  operation-only memory.

jsonmodem made more allocation requests in all 36 cases. For loads, it requested
fewer total bytes and had a smaller tracked peak in all 18 documents. For dumps,
orjson requested fewer bytes and had a smaller tracked peak in all 18 documents.
There is no combined memory score or memory geometric mean.

**The `otfcc` dumps RSS peak was set by input preparation.** All six workers had
already reached their final RSS high-water mark before the first serialization.
The roughly 714 MiB peaks therefore do not show equal serializer memory use.
The separately tracked peaks were 127.334 MiB for jsonmodem and 64.000 MiB for
orjson. Intermediate RSS readings are retained in the result JSON.
[PUBLIC_MEMORY.md](PUBLIC_MEMORY.md) describes those fields and their limits.

### loads: allocation requests

Lower is better. Requests per tracked call.

| Document | jsonmodem baseline (requests) | orjson 3.11.9 (requests) |
| --- | ---: | ---: |
| apache_builds | 4,308 | **4,255** |
| canada | 225,411 | **223,043** |
| citm_catalog | 51,213 | **49,014** |
| github_events | 1,230 | **1,081** |
| google_maps_api_response | 1,024 | **985** |
| gsoc-2018 | 25,164 | **23,200** |
| instruments | 2,797 | **2,490** |
| marine_ik | 257,531 | **255,899** |
| mesh | 74,385 | **74,104** |
| numbers | 9,956 | **9,911** |
| random | 32,564 | **23,519** |
| semanticscholar-corpus | 249,836 | **230,416** |
| tree-pretty | 556 | **467** |
| twitter | 11,551 | **9,237** |
| twitterescaped | 11,551 | **9,237** |
| update-center | 20,803 | **19,583** |
| poet | 80,375 | **44,514** |
| otfcc | 10,276,965 | **7,375,455** |

### loads: total allocated bytes

Lower is better. Total requests during one tracked call.

| Document | jsonmodem baseline (MiB) | orjson 3.11.9 (MiB) |
| --- | ---: | ---: |
| apache_builds | **0.370** | 1.772 |
| canada | **10.487** | 32.568 |
| citm_catalog | **3.263** | 22.819 |
| github_events | **0.136** | 0.848 |
| google_maps_api_response | **0.066** | 0.363 |
| gsoc-2018 | **6.997** | 42.922 |
| instruments | **0.341** | 2.816 |
| marine_ik | **19.262** | 43.584 |
| mesh | **7.048** | 10.733 |
| numbers | **0.943** | 2.022 |
| random | **2.818** | 7.868 |
| semanticscholar-corpus | **27.284** | 121.426 |
| tree-pretty | **0.054** | 0.440 |
| twitter | **1.492** | 8.218 |
| twitterescaped | **1.492** | 7.425 |
| update-center | **1.694** | 7.645 |
| poet | **15.113** | 45.209 |
| otfcc | **622.288** | 1,225.443 |

### loads: tracked peak bytes

Lower is better. Maximum live tracked bytes, excluding preparation and warmups.

| Document | jsonmodem baseline (MiB) | orjson 3.11.9 (MiB) |
| --- | ---: | ---: |
| apache_builds | **0.318** | 1.772 |
| canada | **7.689** | 32.568 |
| citm_catalog | **3.144** | 22.819 |
| github_events | **0.116** | 0.848 |
| google_maps_api_response | **0.064** | 0.362 |
| gsoc-2018 | **4.890** | 42.921 |
| instruments | **0.272** | 2.816 |
| marine_ik | **9.922** | 43.584 |
| mesh | **2.657** | 10.733 |
| numbers | **0.308** | 2.022 |
| random | **1.876** | 7.868 |
| semanticscholar-corpus | **20.332** | 121.426 |
| tree-pretty | **0.040** | 0.440 |
| twitter | **0.892** | 8.218 |
| twitterescaped | **0.892** | 7.425 |
| update-center | **1.516** | 7.644 |
| poet | **5.010** | 45.209 |
| otfcc | **585.970** | 1,225.442 |

### loads: whole-process peak RSS

Lower is better. Includes the interpreter, original input bytes, and all calls.

| Document | jsonmodem baseline (MiB) | orjson 3.11.9 (MiB) |
| --- | ---: | ---: |
| apache_builds | 23.441 | **23.309** |
| canada | **34.250** | 41.547 |
| citm_catalog | **28.312** | 32.316 |
| github_events | 22.992 | **22.484** |
| google_maps_api_response | 23.031 | **22.578** |
| gsoc-2018 | **31.711** | 37.145 |
| instruments | **23.512** | 23.570 |
| marine_ik | **37.078** | 45.855 |
| mesh | **26.922** | 29.457 |
| numbers | 23.629 | **23.242** |
| random | **26.023** | 29.758 |
| semanticscholar-corpus | **53.570** | 71.809 |
| tree-pretty | 23.035 | **22.555** |
| twitter | **24.613** | 26.750 |
| twitterescaped | **24.809** | 26.898 |
| update-center | **26.352** | 27.508 |
| poet | **32.367** | 38.094 |
| otfcc | **707.680** | 874.617 |

### dumps: allocation requests

Lower is better. Requests per tracked call.

| Document | jsonmodem baseline (requests) | orjson 3.11.9 (requests) |
| --- | ---: | ---: |
| apache_builds | 23 | **15** |
| canada | 25 | **20** |
| citm_catalog | 26 | **18** |
| github_events | 23 | **14** |
| google_maps_api_response | 20 | **13** |
| gsoc-2018 | 28 | **18** |
| instruments | 24 | **16** |
| marine_ik | 29 | **20** |
| mesh | 25 | **19** |
| numbers | 20 | **17** |
| random | 26 | **18** |
| semanticscholar-corpus | 31 | **22** |
| tree-pretty | 22 | **13** |
| twitter | 27 | **17** |
| twitterescaped | 27 | **17** |
| update-center | 27 | **19** |
| poet | 24 | **19** |
| otfcc | 34 | **25** |

### dumps: total allocated bytes

Lower is better. Total requests during one tracked call.

| Document | jsonmodem baseline (MiB) | orjson 3.11.9 (MiB) |
| --- | ---: | ---: |
| apache_builds | 0.375 | **0.248** |
| canada | 5.994 | **4.000** |
| citm_catalog | 1.479 | **1.000** |
| github_events | 0.178 | **0.094** |
| google_maps_api_response | 0.044 | **0.031** |
| gsoc-2018 | 13.378 | **7.974** |
| instruments | 0.355 | **0.250** |
| marine_ik | 5.746 | **4.000** |
| mesh | 2.621 | **2.000** |
| numbers | 0.644 | **0.500** |
| random | 1.442 | **1.000** |
| semanticscholar-corpus | 40.192 | **31.996** |
| tree-pretty | 0.048 | **0.031** |
| twitter | 1.514 | **0.998** |
| twitterescaped | 1.514 | **0.998** |
| update-center | 2.510 | **2.000** |
| poet | 9.888 | **7.994** |
| otfcc | 191.336 | **128.000** |

### dumps: tracked peak bytes

Lower is better. Maximum live tracked bytes, excluding preparation and warmups.

| Document | jsonmodem baseline (MiB) | orjson 3.11.9 (MiB) |
| --- | ---: | ---: |
| apache_builds | 0.233 | **0.125** |
| canada | 3.994 | **2.000** |
| citm_catalog | 0.978 | **0.500** |
| github_events | 0.114 | **0.063** |
| google_maps_api_response | 0.027 | **0.016** |
| gsoc-2018 | 8.153 | **4.000** |
| instruments | 0.229 | **0.125** |
| marine_ik | 3.744 | **2.000** |
| mesh | 1.621 | **1.000** |
| numbers | 0.394 | **0.250** |
| random | 0.941 | **0.500** |
| semanticscholar-corpus | 24.191 | **16.000** |
| tree-pretty | 0.031 | **0.016** |
| twitter | 0.979 | **0.500** |
| twitterescaped | 0.979 | **0.500** |
| update-center | 1.509 | **1.000** |
| poet | 6.517 | **4.000** |
| otfcc | 127.334 | **64.000** |

### dumps: whole-process peak RSS

Lower is better. Includes input preparation; the otfcc peak was set before dumps.

| Document | jsonmodem baseline (MiB) | orjson 3.11.9 (MiB) |
| --- | ---: | ---: |
| apache_builds | 23.508 | **22.977** |
| canada | 36.219 | **35.602** |
| citm_catalog | 31.273 | **30.637** |
| github_events | 23.309 | **22.500** |
| google_maps_api_response | 23.031 | **22.461** |
| gsoc-2018 | 35.797 | **34.113** |
| instruments | 23.676 | **23.062** |
| marine_ik | 39.766 | **39.312** |
| mesh | 28.023 | **26.625** |
| numbers | 23.891 | **22.914** |
| random | **26.301** | 26.422 |
| semanticscholar-corpus | 85.625 | **84.984** |
| tree-pretty | 23.172 | **22.422** |
| twitter | 26.582 | **25.996** |
| twitterescaped | 25.324 | **24.484** |
| update-center | 26.289 | **25.605** |
| poet | 38.195 | **37.348** |
| otfcc | 713.828 | **713.332** |

## Reproduce the measurements

Use the pinned fixtures and library configuration described in
[PUBLIC_CORPUS.md](PUBLIC_CORPUS.md#run-a-comparison), selecting the baseline
commit and orjson 3.11.9. Keep each result family in its own output file. These
commands use the recorded CPU IDs; choose available CPUs on another machine.
Stop competing heavy work before collecting final results.

Repeated calls:

```bash
python crates/jsonmodem-py/benchmarks/bench_public_corpus.py run \
  --directory /tmp/jsonmodem-public-corpus --libraries libraries.json \
  --reference orjson_3119 --operations loads dumps --cpu 12 \
  --repeats 8 --samples 3 --seconds 0.05 --warmups 3 \
  --output public-repeated.json
```

Fresh/reused single calls:

```bash
python crates/jsonmodem-py/benchmarks/bench_public_fresh_dumps.py run \
  --directory /tmp/jsonmodem-public-corpus --libraries libraries.json \
  --reference orjson_3119 --conditions fresh reused --cpu 8 \
  --repeats 9 --warmups 10 --output public-single-call.json
```

Separate Memray and RSS measurements:

```bash
python crates/jsonmodem-py/benchmarks/bench_public_memory.py run \
  --directory /tmp/jsonmodem-public-corpus --libraries libraries.json \
  --reference orjson_3119 --operations loads dumps --metrics memray rss \
  --cpu 8 --repeats 3 --calls 1 --warmups 10 --rss-calls 10 \
  --memray-version 1.20.0 --profiles /tmp/jsonmodem-public-memory \
  --output public-memory.json
```

All three runners check fixture hashes and complete outputs before accepting
results. Correctness on these documents is not a full compatibility or security
test. The data-source terms and unresolved redistribution rights are recorded in
the [corpus documentation](PUBLIC_CORPUS.md#data-terms); no third-party documents
are included in this report.

### Recorded fingerprints

These SHA-256 values identify the files used for the captures. Library and
interpreter hashes match across all three comparisons. The version of
`bench_public_corpus.py` used for the first capture differs from the current
file only in a progress message; its timing body is unchanged.
`bench_public_fresh_dumps.py` and `bench_public_memory.py` implement the different
methods described above.

<details>
<summary>SHA-256 fingerprints</summary>

```text
CPython executable
7d43f6e86a6c6dd12005ec77eb2055f1be3f1bb3adedf8afe0a87973fa7371ce
jsonmodem native extension
5b1ab812d74c1df4c60d87e3d194c29c140a179a5e7bd2948a4fb6ea61d11ebe
jsonmodem wheel (supplied build identifier)
51e493282dab7c0f60b37eab3a8e34c7167fa72a1f89a660d10b962474b8110b
orjson native extension
cf95e4edd9c6752be617f8afc1f08bfd6b015007520e15069e56c102ffb9d295
public_corpus_manifest.json
91dea3195ba691037f43399f927f5747ddb1dd80f5cc3e84db386f2bca7ddb30
public_corpus.py
6a7ba7893d0e3ec83ef0cd70043eb29893eb2e8a7730476dcf02c0ec8cc9505c
bench_public_corpus.py at the repeated-call capture
8ea099d4632567124eaf2f905431b15523d298e03a92aa91cb5b956c80d81293
bench_public_corpus.py shared by the later runners
b00c361b29535abfc16548de41a32a5d4caa0737e4989d80991c1d9041a9bbe9
bench_public_fresh_dumps.py
9a6d4a4dd1153ff39feac08534237551170a7eab1924ab49cd88aa4c466d764d
bench_public_memory.py
883761e77126b07ed40ae4c818f67ec0e7416bae947ec75ca92bcd6824dbeb9d
allocation_stats.py
811f04e52c2177df802cf45589ab02a15f5c25260815c3975af07bbeafe86f15
```

</details>
