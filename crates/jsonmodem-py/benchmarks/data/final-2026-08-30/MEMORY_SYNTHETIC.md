# Synthetic memory

Original is the existing PR #3 build; Rebuilt compiles that same source
again (`b7fe329`).
Final is the changed implementation (`b0f3190`).
The reference is orjson 3.11.9. See [definitions and methods](README.md).

[Summary](PERFORMANCE_FINAL.md). Medians of three process observations.
Memray uses one tracked call after ten warmups.
Peak live bytes are Memray's reported capture peak, not process RSS or a separate reconstruction.
RSS uses ten calls without warmup. Peak RSS is Linux VmHWM, including preparation; it is not ru_maxrss.
Four libraries and three repetitions do not fully balance execution positions. There is no memory mean.

Allocation requests (requests). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads_medium` | 4,762 | 4,762 | 4,762 | **4,732** |
| `dumps_small` | 11 | 11 | 11 | **10** |
| `dumps_medium` | 20 | 20 | 20 | **16** |
| `long_string` | **10** | **10** | **10** | 11 |
| `sorted_medium` | 1,022 | 1,022 | 1,022 | **1,018** |
| `fragments_1000` | 17 | 17 | 17 | **14** |
| `dataclasses_1000` | 22 | 22 | 22 | **15** |
| `numpy_float32` | **45** | **45** | **45** | 25,041 |
| `late_default` | 31 | 31 | 31 | **23** |
| `loads_small_array_view` | 16 | 16 | 16 | **15** |
| `loads_small` | **15** | **15** | **15** | **15** |
| `loads_medium_array_view` | 4,779 | 4,779 | 4,779 | **4,748** |
| `loads_long_string_array_view` | **11** | **11** | **11** | **11** |
| `loads_long_string` | **10** | **10** | **10** | 11 |

Total allocated bytes (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads_medium` | **341.101** | **341.101** | **341.101** | 906.110 |
| `dumps_small` | **0.723** | **0.723** | **0.723** | 1.415 |
| `dumps_medium` | 180.499 | 180.499 | 180.499 | **127.608** |
| `long_string` | **140.417** | **140.417** | **140.417** | 2,049.447 |
| `sorted_medium` | 243.140 | 243.140 | 243.140 | **198.062** |
| `fragments_1000` | 45.838 | 45.838 | 45.838 | **31.544** |
| `dataclasses_1000` | 100.266 | 100.266 | 100.266 | **63.576** |
| `numpy_float32` | **3,196.432** | **3,196.432** | **3,196.432** | 7,558.495 |
| `late_default` | 85,634.756 | 85,634.756 | 85,634.756 | **65,474.019** |
| `loads_small_array_view` | **0.725** | **0.725** | **0.725** | 4.578 |
| `loads_small` | **0.635** | **0.635** | **0.635** | 4.578 |
| `loads_medium_array_view` | **394.186** | **394.186** | **394.186** | 906.923 |
| `loads_long_string_array_view` | **280.457** | **280.457** | **280.457** | 1,824.423 |
| `loads_long_string` | **140.423** | **140.423** | **140.423** | 1,824.423 |

Peak live bytes tracked by Memray (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads_medium` | **281.637** | **281.637** | **281.637** | 905.678 |
| `dumps_small` | **0.379** | **0.379** | **0.379** | 1.103 |
| `dumps_medium` | 116.405 | 116.405 | 116.405 | **64.103** |
| `long_string` | **140.104** | **140.104** | **140.104** | 2,048.103 |
| `sorted_medium` | 116.546 | 116.546 | 116.546 | **64.282** |
| `fragments_1000` | 29.744 | 29.744 | 29.744 | **16.103** |
| `dataclasses_1000` | 60.311 | 60.311 | 60.311 | **32.103** |
| `numpy_float32` | **2,234.950** | **2,234.950** | **2,234.950** | 3,974.985 |
| `late_default` | 52,806.905 | 52,806.905 | 52,806.905 | **32,768.353** |
| `loads_small_array_view` | **0.381** | **0.381** | **0.381** | 4.234 |
| `loads_small` | **0.322** | **0.322** | **0.322** | 4.234 |
| `loads_medium_array_view` | **334.722** | **334.722** | **334.722** | 906.490 |
| `loads_long_string_array_view` | **280.113** | **280.113** | **280.113** | 1,824.079 |
| `loads_long_string` | **140.110** | **140.110** | **140.110** | 1,824.079 |

Peak RSS, including preparation (Linux VmHWM) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads_medium` | 18.676 | 18.832 | 18.820 | **18.133** |
| `loads_large` | 55.383 | **55.348** | 55.441 | 70.738 |
| `dumps_medium` | 18.715 | 18.574 | 18.797 | **17.871** |
| `fragments_1000` | 17.613 | 17.402 | 18.461 | **17.191** |
| `dataclasses_1000` | 18.512 | 18.422 | 18.863 | **17.816** |
| `numpy_float32` | 35.559 | **35.391** | 35.453 | 36.102 |
| `late_default` | 57.695 | 57.609 | 57.836 | **37.414** |

Prepared RSS (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads_medium` | 17.574 | 17.609 | 18.457 | **17.258** |
| `loads_large` | 23.730 | 23.703 | 23.910 | **23.090** |
| `dumps_medium` | 18.398 | 18.199 | 18.797 | **17.871** |
| `fragments_1000` | 17.613 | 17.402 | 18.461 | **17.191** |
| `dataclasses_1000` | 18.512 | 18.422 | 18.500 | **17.816** |
| `numpy_float32` | 33.242 | 33.109 | 33.082 | **32.570** |
| `late_default` | 18.527 | 18.523 | 18.496 | **17.387** |

Synthetic allocation cases share worker history and keep cyclic GC enabled; public/target memory disables it during observation.
Synthetic RSS does not retain the first result for a snapshot. Do not pool these observations with the other memory suites.
