# Additional memory measurements

This report compares unchanged jsonmodem at
`b7fe329765f3e90064cc38f127d3594165116c71` with **orjson 3.11.9**. It adds
14 synthetic allocation workloads, seven RSS workloads, and the first
serialization of three public documents to the
[public baseline](PUBLIC_BASELINE.md).

Measurements used CPython 3.12.13, Memray 1.20.0, and NumPy 2.5.2 on Linux
x86_64, on 2026-08-29. Processes were pinned to CPU 8, with other workers' heavy
jobs paused. This does not imply exclusive control of all host background
processes. CPU model and clock settings were not recorded.

Tables show the median of three results per library and workload. **Bold marks
the lower recorded median, including ties**, not statistical significance.
Memory cells use the same unit within each row: KiB = 1,024 bytes and
MiB = 1,048,576 bytes. [Result data](data/supplemental-memory-2026-08-29/README.md)
retains every repeat, verification result, and fingerprint. No overall memory
score is calculated.

## Synthetic workloads

Names starting with `loads_` decode JSON; the other workloads serialize Python
values. The unchanged [allocation](bench_allocations.py) and
[RSS](bench_rss.py) drivers define the inputs:

- `loads_medium`, `dumps_medium`, and `sorted_medium`: 1,000 dictionaries with
  `id=i`, `score=i/7`, and `name=f"item-{i}"`, for `i` from 0 through 999.
  Compact JSON is 53,494 bytes. `sorted_medium` sorts each dictionary's keys.
- `loads_large`, used only for RSS: 100,000 dictionaries of the same form;
  5,752,011 input bytes. A separate process generates the encoded input, so the
  loads worker does not retain a decoded reference tree.
- `loads_small` and `dumps_small`: a four-key dictionary with an integer,
  Boolean, string, and three-string list; 59 JSON bytes.
- `long_string` and `loads_long_string`: 143,360 ASCII characters;
  143,362 JSON bytes including quotes.
- The three `loads_*_array_view` workloads use the small, medium, or long-string
  JSON above through `memoryview(array.array("B", document))`.
- `fragments_1000`: 1,000 references to a fragment containing `{"x":[1,2,3]}`;
  14,001 output bytes.
- `dataclasses_1000`: 1,000 dataclass records with integer `id` and string `name`;
  28,781 output bytes.
- `numpy_float32`: 100,000 contiguous float32 values, from 0 through 99,999,
  arranged as 25,000 rows of four; 400,000 array-storage bytes and 838,891 output
  bytes. Serialization uses `OPT_SERIALIZE_NUMPY`.
- `late_default`: 5,000 references to one 4,096-character ASCII string, followed
  by an unsupported object. A `default` callback returns `None` for that last
  object. Output is 20,495,006 bytes.

## Synthetic allocations

Each library ran in three fresh Python processes. Each process prepared all
14 workloads, then captured them sequentially. Workloads therefore share
process history within each repeat; these are not fresh processes per workload.
There are 84 captures in total.

For each workload, the driver makes ten warmup calls, collects cyclic GC, and
tracks one call with Memray. Cyclic GC remains enabled. Each returned result is
released before the next call; result release is included in the capture.
Input preparation, preexisting allocations, and warmup allocations are excluded.
Python allocator tracing is enabled and native stack collection is disabled.
All synthetic allocation metrics were identical across the three repeats.

Allocation requests count allocating calls, including zero-byte requests.
Deallocation records are excluded even when they contain a positive size.
Total allocated bytes sum requested sizes, including each realloc's full new
size. Tracked peak is Memray's maximum live bytes during the call. Neither
quantity is process RSS.

### Allocation requests

Lower is better. Requests during one tracked call.

| Workload | jsonmodem baseline | orjson 3.11.9 |
| --- | ---: | ---: |
| loads_medium | 4,762 | **4,732** |
| dumps_small | 11 | **10** |
| dumps_medium | 20 | **16** |
| long_string | **10** | 11 |
| sorted_medium | 1,022 | **1,018** |
| fragments_1000 | 17 | **14** |
| dataclasses_1000 | 22 | **15** |
| numpy_float32 | **45** | 25,041 |
| late_default | 31 | **23** |
| loads_small_array_view | 16 | **15** |
| loads_small | **15** | **15** |
| loads_medium_array_view | 4,779 | **4,748** |
| loads_long_string_array_view | **11** | **11** |
| loads_long_string | **10** | 11 |

### Total allocated bytes

Lower is better. Cumulative requested memory during one tracked call.

| Workload | jsonmodem baseline | orjson 3.11.9 |
| --- | ---: | ---: |
| loads_medium | **341.101 KiB** | 906.110 KiB |
| dumps_small | **0.723 KiB** | 1.415 KiB |
| dumps_medium | 180.499 KiB | **127.608 KiB** |
| long_string | **0.137 MiB** | 2.001 MiB |
| sorted_medium | 243.140 KiB | **198.062 KiB** |
| fragments_1000 | 45.838 KiB | **31.544 KiB** |
| dataclasses_1000 | 100.266 KiB | **63.576 KiB** |
| numpy_float32 | **3.122 MiB** | 7.381 MiB |
| late_default | 83.628 MiB | **63.939 MiB** |
| loads_small_array_view | **0.725 KiB** | 4.578 KiB |
| loads_small | **0.635 KiB** | 4.578 KiB |
| loads_medium_array_view | **394.186 KiB** | 906.923 KiB |
| loads_long_string_array_view | **0.274 MiB** | 1.782 MiB |
| loads_long_string | **0.137 MiB** | 1.782 MiB |

### Tracked peak bytes

Lower is better. Maximum live tracked memory, excluding preparation and warmups.

| Workload | jsonmodem baseline | orjson 3.11.9 |
| --- | ---: | ---: |
| loads_medium | **281.637 KiB** | 905.678 KiB |
| dumps_small | **0.379 KiB** | 1.103 KiB |
| dumps_medium | 116.405 KiB | **64.103 KiB** |
| long_string | **0.137 MiB** | 2.000 MiB |
| sorted_medium | 116.546 KiB | **64.282 KiB** |
| fragments_1000 | 29.744 KiB | **16.103 KiB** |
| dataclasses_1000 | 60.311 KiB | **32.103 KiB** |
| numpy_float32 | **2.183 MiB** | 3.882 MiB |
| late_default | 51.569 MiB | **32.000 MiB** |
| loads_small_array_view | **0.381 KiB** | 4.234 KiB |
| loads_small | **0.322 KiB** | 4.234 KiB |
| loads_medium_array_view | **334.722 KiB** | 906.490 KiB |
| loads_long_string_array_view | **0.274 MiB** | 1.781 MiB |
| loads_long_string | **0.137 MiB** | 1.781 MiB |

## Synthetic peak RSS

RSS measures whole-process resident memory in separate workers without Memray.
Each library/workload pair uses three fresh workers, for 42 workers total.
Each worker prepares one workload, collects cyclic GC, and makes ten calls
without preliminary warmups. GC stays enabled. Results are released before RSS
snapshots. The reported peak is not divided by the number of calls.

These peaks include the interpreter, imports, input preparation, results, and
retained allocator pages. **Preparation already set the final peak for every
`fragments_1000` and `dataclasses_1000` worker, for both libraries.** It also set
the peak for every orjson `dumps_medium` worker. Their small RSS differences do
not measure serializer-only memory. Subtracting starting RSS does not reset the
process high-water mark.

Lower is better. Whole-process peak RSS after ten calls, including preparation.

| Workload | jsonmodem baseline | orjson 3.11.9 |
| --- | ---: | ---: |
| loads_medium | 18.734 MiB | **17.988 MiB** |
| loads_large | **55.559 MiB** | 72.910 MiB |
| dumps_medium | 18.676 MiB | **17.848 MiB** |
| fragments_1000 | 17.488 MiB | **17.227 MiB** |
| dataclasses_1000 | 18.312 MiB | **17.812 MiB** |
| numpy_float32 | **35.395 MiB** | 36.066 MiB |
| late_default | 60.477 MiB | **37.965 MiB** |

## First serialization of public documents

These separate Memray captures track the worker's first `dumps()` call, with
zero warmups. Each document/library pair uses three fresh processes, for
18 captures. Standard-library `json.loads()` prepares one input outside the
capture; the original encoded bytes are then released. GC is collected and
disabled before capture, unlike the synthetic drivers. The returned bytes are
released inside the capture. No correctness reference tree is retained in the
worker.

The inputs are the pinned public documents: `numbers`, an array of floats
(150,124 source bytes); `twitterescaped`, Twitter data with Unicode escapes
(562,408 bytes); and `poet`, Chinese author biographies (3,512,883 bytes).
See [sources and data terms](PUBLIC_CORPUS.md#data-terms). The source byte counts
describe the original files, not the size of the prepared Python values.

### First-call allocation requests

Lower is better. Requests during one tracked call, with zero warmups.

| Workload | jsonmodem baseline | orjson 3.11.9 |
| --- | ---: | ---: |
| numbers | 20 | **17** |
| twitterescaped | 785 | **775** |
| poet | 19,456 | **19,451** |

### First-call total allocated bytes

Lower is better. Cumulative requested memory during one tracked call.

| Workload | jsonmodem baseline | orjson 3.11.9 |
| --- | ---: | ---: |
| numbers | 0.644 MiB | **0.500 MiB** |
| twitterescaped | 1.621 MiB | **1.104 MiB** |
| poet | 13.730 MiB | **11.836 MiB** |

### First-call tracked peak bytes

Lower is better. Maximum live tracked memory, excluding input preparation.

| Workload | jsonmodem baseline | orjson 3.11.9 |
| --- | ---: | ---: |
| numbers | 0.394 MiB | **0.250 MiB** |
| twitterescaped | 1.084 MiB | **0.605 MiB** |
| poet | 9.118 MiB | **6.601 MiB** |

Compared with [the earlier ten-warmup captures](PUBLIC_BASELINE.md#initial-memory-measurements),
`numbers` was unchanged in all three allocation metrics for both libraries.
First-use `twitterescaped` added exactly 758 requests, 111,645 requested bytes,
and 109,870 tracked peak bytes to each library. `poet` added exactly
19,432 requests, 4,028,610 requested bytes, and 2,726,683 tracked peak bytes to
each library.

Those are first-call observations, including possible library initialization
and first-use string allocations. They do not isolate UTF-8 caches. The earlier
warmed captures also permitted concurrent builds and correctness checks; keep
that limitation when comparing them with these captures. This is not the
[fresh/reused timing experiment](PUBLIC_FRESH_DUMPS.md), which warms the library
on a separate value before preparing fresh timed input.

## Reproduce the captures

Use an environment containing the versions and jsonmodem commit above. Check
imported files against the [recorded fingerprints](data/supplemental-memory-2026-08-29/README.md)
and stop competing heavy work. These commands use CPU 8; select an available CPU
on another machine. Keep new captures outside the repository and do not reuse
existing output filenames.

The recorded run checked complete outputs and fingerprints before and after
capture in separate processes. The synthetic drivers do not perform those
complete-output checks themselves. The public-document runner does.

Synthetic allocations, with three process repeats and alternating library order:

```bash
output=/tmp/jsonmodem-supplemental-memory
mkdir -p "$output"
for repeat in 1 2 3; do
  if [ "$repeat" -eq 2 ]; then
    modules="orjson jsonmodem"
  else
    modules="jsonmodem orjson"
  fi
  for module in $modules; do
    env -u PYTHONPATH -u PYTHONHOME PYTHONNOUSERSITE=1 \
      PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=$((1728 + repeat)) \
      taskset -c 8 python crates/jsonmodem-py/benchmarks/bench_allocations.py \
      --module "$module" --calls 1 --output "$output/$module-$repeat.json"
  done
done
```

Synthetic RSS, using the same environment:

```bash
env -u PYTHONPATH -u PYTHONHOME PYTHONNOUSERSITE=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=1729 taskset -c 8 \
  python crates/jsonmodem-py/benchmarks/bench_rss.py \
  --runs 3 --calls 10 --output /tmp/jsonmodem-supplemental-memory/rss.json
```

First-use public documents, using the verified fixtures and library configuration
from [PUBLIC_CORPUS.md](PUBLIC_CORPUS.md#run-a-comparison):

```bash
env -u PYTHONPATH -u PYTHONHOME PYTHONNOUSERSITE=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=1729 taskset -c 8 \
  python crates/jsonmodem-py/benchmarks/bench_public_memory.py run \
  --directory /tmp/jsonmodem-public-corpus --libraries libraries.json \
  --reference orjson_3119 --operations dumps --metrics memray \
  --cases numbers poet twitterescaped --cpu 8 --repeats 3 \
  --calls 1 --warmups 0 --memray-version 1.20.0 \
  --profiles /tmp/jsonmodem-supplemental-memory/first-use \
  --output /tmp/jsonmodem-supplemental-memory/first-use.json
```
