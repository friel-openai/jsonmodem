# Final performance measurements

Original is the previously tested build at `b0f3190`.
Rebuilt is a new compilation of the same runtime source at `3279ba1`.
Final uses the tested source at `b889f4c`. Full revisions and build hashes are in [data.json](data.json).
The reference is orjson 3.11.9 on CPython 3.12.13. These are repeated-call measurements, not startup measurements.

## Absolute geometric means

For each case, take the median of the process medians. The geometric mean combines those case latencies with equal case weights.
Each process median uses three samples. Public runs use eight processes per build; maintained runs use seven; date/NumPy runs use eight.
Each paired process measures one jsonmodem build and orjson. Its orjson observations stay separate from the other build's processes.
Suites and unchanged-control comparisons stay separate. These means are not the time to run a combined workload.

Public documents: geometric mean latency (us per complete call). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| Loads (18 cases) | 2,351.524 | 2,352.985 | 2,220.319 | **1,560.490** |
| Dumps (18 cases) | 1,038.946 | 1,038.833 | 883.634 | **473.640** |
| Combined (36 cases) | 1,563.043 | 1,563.444 | 1,400.696 | **859.715** |

Maintained suite, original control: geometric mean latency (us per complete call). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| Loads (106 cases) | 39.283 | 36.067 | **32.732** | 32.830 |
| Dumps (65 cases) | 23.571 | 22.045 | **15.693** | 15.814 |
| Combined (171 cases) | 32.351 | 29.911 | **24.752** | 24.871 |

Maintained suite, rebuilt control: geometric mean latency (us per complete call). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| Loads (106 cases) | 39.351 | 35.985 | **32.766** | 32.796 |
| Dumps (65 cases) | 23.793 | 22.054 | **15.759** | 15.759 |
| Combined (171 cases) | 32.501 | 29.874 | **24.808** | 24.822 |

Date/time and NumPy, original control: geometric mean dumps latency (us per complete call). Only byte-equivalent outputs. Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| Date/time (40 cases) | 21.181 | 18.710 | **11.687** | 11.742 |
| NumPy (28 cases) | 21.043 | **20.964** | 22.945 | 23.008 |

Date/time and NumPy, rebuilt control: geometric mean dumps latency (us per complete call). Only byte-equivalent outputs. Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| Date/time (40 cases) | 21.206 | 18.696 | 11.750 | **11.725** |
| NumPy (28 cases) | 21.102 | **20.864** | 22.860 | 23.005 |

## Relative to orjson

These secondary comparisons use the same cases and medians. A ratio of 1 means equal latency; 2 means twice the time. Lower is better.
Take the geometric mean of case latency divided by its corresponding orjson latency. These are not medians of paired ratios.

Public documents: latency ratios versus orjson. Lower is better.

| Case | Original/orjson | Rebuilt/orjson | Final/orjson |
| --- | ---: | ---: | ---: |
| Loads (18 cases) | 1.5069 | 1.5078 | **1.4228** |
| Dumps (18 cases) | 2.1935 | 2.1933 | **1.8656** |
| Combined (36 cases) | 1.8181 | 1.8186 | **1.6293** |

Maintained suite: each build uses orjson measured in its own worker processes. Lower is better.

| Case | Control/orjson | Final/orjson |
| --- | ---: | ---: |
| Original: loads (106 cases) | 1.2001 | **1.0986** |
| Original: dumps (65 cases) | 1.5020 | **1.3940** |
| Original: combined (171 cases) | 1.3070 | **1.2027** |
| Rebuilt: loads (106 cases) | 1.2010 | **1.0972** |
| Rebuilt: dumps (65 cases) | 1.5098 | **1.3995** |
| Rebuilt: combined (171 cases) | 1.3101 | **1.2035** |

Targets: only byte-equivalent outputs enter these orjson ratios. Lower is better.

| Case | Control/orjson | Final/orjson |
| --- | ---: | ---: |
| Date/time, original control (40 cases) | 1.8124 | **1.5934** |
| Date/time, rebuilt control (40 cases) | 1.8048 | **1.5945** |
| NumPy, original control (28 cases) | 0.9171 | **0.9111** |
| NumPy, rebuilt control (28 cases) | 0.9231 | **0.9069** |

## All cases

No slower case is omitted. Case tables show absolute values; bold uses unrounded minima.

- [Public documents: all 36 operations](PUBLIC.md).
- Maintained 171 cases: [original control](MAINTAINED_ORIGINAL.md), [rebuilt control](MAINTAINED_REBUILT.md).
- Dates: 40 equivalent cases and three visible unequal-output cases: [original control](DATES_ORIGINAL.md), [rebuilt control](DATES_REBUILT.md).
- NumPy: all 28 cases: [original control](NUMPY_ORIGINAL.md), [rebuilt control](NUMPY_REBUILT.md).
- Incremental APIs: [original control](INCREMENTAL_ORIGINAL.md), [rebuilt control](INCREMENTAL_REBUILT.md).
- [Malformed inputs: all 39 cases, latency and Memray](MALFORMED.md). No rejection score is combined with successful parsing.
- Memory: [public](MEMORY_PUBLIC.md), [synthetic](MEMORY_SYNTHETIC.md), [dates](MEMORY_DATES.md), [NumPy](MEMORY_NUMPY.md).

Allocation requests, allocated bytes, tracked peak bytes, and process RSS are different quantities; there is no memory mean.
RSS includes preparation and may peak before a measured call. Three memory repetitions do not fully balance four library positions.

[Portable observations, table data, and build identities](data.json). Available per-process samples and call counts are retained; capture binaries and logs remain private.
