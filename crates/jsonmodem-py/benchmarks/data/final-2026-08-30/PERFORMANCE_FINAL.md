# Final performance measurements

Original and Rebuilt use the same PR #3 source at `b7fe329`; Rebuilt is a new compilation.
Final uses the tested source at `b0f3190`. Full revisions and build hashes are in [data.json](data.json).
The reference is orjson 3.11.9 on CPython 3.12.13. These are repeated-call measurements, not startup measurements.

## Absolute geometric means

For each case, take the median of the process medians. The geometric mean combines those case latencies with equal case weights.
Each process median uses three samples. Public runs use eight processes per build; maintained runs use seven; date/NumPy datetime64 runs use eight.
Each paired process measures one jsonmodem build and orjson. Its orjson observations stay separate from the other build's processes.
Suites and unchanged-control comparisons stay separate. These means are not the time to run a combined workload.

Public documents: geometric mean latency (us per complete call). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| Loads (18 cases) | 2,344.357 | 2,327.939 | 2,352.351 | **1,621.712** |
| Dumps (18 cases) | 1,066.430 | 1,050.490 | 1,051.258 | **478.329** |
| Combined (36 cases) | 1,581.168 | 1,563.802 | 1,572.554 | **880.745** |

Maintained suite, original control: geometric mean latency (us per complete call). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| Loads (106 cases) | 39.599 | 39.280 | 32.795 | **32.727** |
| Dumps (65 cases) | 23.352 | 23.556 | **15.653** | 15.690 |
| Combined (171 cases) | 32.397 | 32.342 | 24.758 | **24.748** |

Maintained suite, rebuilt control: geometric mean latency (us per complete call). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| Loads (106 cases) | 39.334 | 39.269 | **32.634** | 32.731 |
| Dumps (65 cases) | 23.418 | 23.562 | 15.779 | **15.699** |
| Combined (171 cases) | 32.297 | 32.339 | 24.758 | **24.756** |

Date/time and NumPy datetime64, original control: geometric mean dumps latency (us per complete call). Only byte-equivalent outputs. Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| Date/time (40 cases) | 236.588 | 21.055 | 11.712 | **11.692** |
| NumPy datetime64 (28 cases) | 70.620 | **21.102** | 23.016 | 22.972 |

Date/time and NumPy datetime64, rebuilt control: geometric mean dumps latency (us per complete call). Only byte-equivalent outputs. Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| Date/time (40 cases) | 237.959 | 21.162 | 11.807 | **11.742** |
| NumPy datetime64 (28 cases) | 70.511 | **21.101** | 22.984 | 22.960 |

## Relative to orjson

These secondary comparisons use the same cases and medians. A ratio of 1 means equal latency; 2 means twice the time. Lower is better.
Take the geometric mean of case latency divided by its corresponding orjson latency. These are not medians of paired ratios.

Public documents: latency ratios versus orjson. Lower is better.

| Case | Original/orjson | Rebuilt/orjson | Final/orjson |
| --- | ---: | ---: | ---: |
| Loads (18 cases) | 1.4456 | **1.4355** | 1.4505 |
| Dumps (18 cases) | 2.2295 | **2.1962** | 2.1978 |
| Combined (36 cases) | 1.7953 | **1.7755** | 1.7855 |

Maintained suite: each build uses orjson measured in its own worker processes. Lower is better.

| Case | Control/orjson | Final/orjson |
| --- | ---: | ---: |
| Original: loads (106 cases) | 1.2075 | **1.2002** |
| Original: dumps (65 cases) | **1.4919** | 1.5013 |
| Original: combined (171 cases) | 1.3086 | **1.3068** |
| Rebuilt: loads (106 cases) | 1.2053 | **1.1997** |
| Rebuilt: dumps (65 cases) | **1.4841** | 1.5009 |
| Rebuilt: combined (171 cases) | **1.3045** | 1.3063 |

Targets: only byte-equivalent outputs enter these orjson ratios. Lower is better.

| Case | Control/orjson | Final/orjson |
| --- | ---: | ---: |
| Date/time, original control (40 cases) | 20.2008 | **1.8008** |
| Date/time, rebuilt control (40 cases) | 20.1533 | **1.8022** |
| NumPy datetime64, original control (28 cases) | 3.0683 | **0.9186** |
| NumPy datetime64, rebuilt control (28 cases) | 3.0678 | **0.9190** |

## All cases

No slower case is omitted. Case tables show absolute values; bold uses unrounded minima.

- [Public documents: all 36 operations](PUBLIC.md).
- Maintained 171 cases: [original control](MAINTAINED_ORIGINAL.md), [rebuilt control](MAINTAINED_REBUILT.md).
- Dates: 40 equivalent cases and three visible unequal-output cases: [original control](DATES_ORIGINAL.md), [rebuilt control](DATES_REBUILT.md).
- NumPy datetime64: all 28 cases: [original control](NUMPY_ORIGINAL.md), [rebuilt control](NUMPY_REBUILT.md).
- Incremental APIs: [original control](INCREMENTAL_ORIGINAL.md), [rebuilt control](INCREMENTAL_REBUILT.md).
- [Malformed inputs: all 39 cases, latency and Memray](MALFORMED.md). No rejection score is combined with successful parsing.
- Memory: [public](MEMORY_PUBLIC.md), [synthetic](MEMORY_SYNTHETIC.md), [dates](MEMORY_DATES.md), [NumPy datetime64](MEMORY_NUMPY.md).

Allocation requests, allocated bytes, tracked peak bytes, and process RSS are different quantities; there is no memory mean.
RSS includes preparation and may peak before a measured call. Three memory repetitions do not fully balance four library positions.

[Portable observations, table data, and build identities](data.json). Available per-process samples and call counts are retained; capture binaries and logs are not included.
