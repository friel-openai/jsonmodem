# jsonmodem memory comparisons

Both suites measure jsonmodem `96318df` and orjson 3.11.9. The main suite
uses PR #6 as its older jsonmodem control. The NumPy-container supplement
uses commit `7b7e21c`. These controls are different and are not pooled.

Full measured runtime identities are in memory.json. Publication revisions
are recorded separately and do not replace measured runtime revisions.

Each Memray result covers thirty discarded calls after ten warmup calls
and garbage collection. Inputs exist before tracking. Memray 1.20.0 tracks
native and Python allocator requests, including the capture loop.

Each RSS cell is the median of three fresh processes making ten discarded
calls after garbage collection, with no warmup and no Memray import.
Inputs exist before the pre-call reading. The library is already loaded.
First and final readings follow result disposal; no result is retained.

Displayed values are rounded; bold uses the unrounded counters.
memory.json retains exact counters, all RSS samples and their medians.

## Main suite

An array view means `memoryview(array.array("B", document))`, backed
by a byte array rather than a NumPy array.

### Allocation requests across thirty calls

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem PR #6 | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | 135,842 | 138,169 | **134,942** |
| Encode a small object | 127 | 127 | **97** |
| Encode 1,000 records | 397 | 397 | **277** |
| Encode a long string | **97** | **97** | 127 |
| Encode 1,000 records, sorted keys | 30,457 | 30,457 | **30,337** |
| Encode 1,000 fragments | 307 | 307 | **217** |
| Encode 1,000 two-field dataclasses | 457 | 457 | **247** |
| Encode a 25,000 x 4 float32 array (100,000 values) | **1,147** | **1,147** | 751,027 |
| Large output followed by a callback | 727 | 757 | **487** |
| Decode a small object from an array view | 277 | 337 | **247** |
| Decode a small object | **247** | 307 | **247** |
| Decode 1,000 records from an array view | 135,888 | 138,211 | **134,958** |
| Decode a long string from an array view | **127** | **127** | **127** |
| Decode a long string | **97** | **97** | 127 |

### Total requested memory across thirty calls, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem PR #6 | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | **9.551** | 10.040 | 26.104 |
| Encode a small object | **0.012** | **0.012** | 0.032 |
| Encode 1,000 records | 5.279 | 5.279 | **3.729** |
| Encode a long string | **4.105** | **4.105** | 60.033 |
| Encode 1,000 records, sorted keys | 7.114 | 7.114 | **5.794** |
| Encode 1,000 fragments | 1.334 | 1.334 | **0.915** |
| Encode 1,000 two-field dataclasses | 2.928 | 2.935 | **1.854** |
| Encode a 25,000 x 4 float32 array (100,000 values) | **93.636** | 93.637 | 221.431 |
| Large output followed by a callback | 2,508.822 | 3,469.526 | **1,918.175** |
| Decode a small object from an array view | **0.012** | 0.016 | 0.125 |
| Decode a small object | **0.010** | 0.013 | 0.125 |
| Decode 1,000 records from an array view | **11.083** | 11.572 | 26.105 |
| Decode a long string from an array view | **8.207** | **8.207** | 53.441 |
| Decode a long string | **4.105** | **4.105** | 53.441 |

### Peak tracked live memory, KiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem PR #6 | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | **283.059** | 301.055 | 907.100 |
| Encode a small object | **0.379** | **0.379** | 1.103 |
| Encode 1,000 records | 116.405 | 116.405 | **64.103** |
| Encode a long string | **140.104** | **140.104** | 2,048.103 |
| Encode 1,000 records, sorted keys | 119.944 | 119.944 | **67.681** |
| Encode 1,000 fragments | 29.744 | 29.744 | **16.103** |
| Encode 1,000 two-field dataclasses | 60.311 | 40.017 | **32.103** |
| Encode a 25,000 x 4 float32 array (100,000 values) | **2,238.349** | 2,238.356 | 3,978.384 |
| Large output followed by a callback | 52,810.304 | 32,834.860 | **32,771.751** |
| Decode a small object from an array view | **0.381** | 3.896 | 4.234 |
| Decode a small object | **0.322** | 3.838 | 4.234 |
| Decode 1,000 records from an array view | **335.331** | 353.577 | 907.100 |
| Decode a long string from an array view | **280.113** | **280.113** | 1,824.079 |
| Decode a long string | **140.110** | **140.110** | 1,824.079 |

### Whole-process peak RSS, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem PR #6 | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | 21.320 | 21.332 | **20.246** |
| Decode 100,000 records | **57.512** | 57.629 | 72.887 |
| Encode 1,000 records | 21.223 | 21.254 | **20.160** |
| Encode 1,000 fragments | 21.242 | 21.207 | **19.902** |
| Encode 1,000 two-field dataclasses | 21.254 | 21.277 | **20.262** |
| Encode a 25,000 x 4 float32 array (100,000 values) | **37.480** | 37.711 | 37.758 |
| Large output followed by a callback | 60.684 | 56.371 | **40.238** |

### RSS before calls, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem PR #6 | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | 20.695 | 20.684 | **19.949** |
| Decode 100,000 records | 26.000 | 26.059 | **25.312** |
| Encode 1,000 records | 20.820 | 20.871 | **20.160** |
| Encode 1,000 fragments | 20.645 | 20.582 | **19.902** |
| Encode 1,000 two-field dataclasses | 20.641 | 20.660 | **19.945** |
| Encode a 25,000 x 4 float32 array (100,000 values) | 35.184 | 35.133 | **34.625** |
| Large output followed by a callback | 20.633 | 20.680 | **19.938** |

### RSS after ten calls, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem PR #6 | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | 21.012 | 21.059 | **20.246** |
| Decode 100,000 records | 29.973 | 30.199 | **29.230** |
| Encode 1,000 records | 20.820 | 20.871 | **20.160** |
| Encode 1,000 fragments | 20.645 | 20.582 | **19.902** |
| Encode 1,000 two-field dataclasses | 20.980 | 21.035 | **20.262** |
| Encode a 25,000 x 4 float32 array (100,000 values) | **35.680** | 35.910 | 37.758 |
| Large output followed by a callback | 40.270 | 36.824 | **20.914** |

## NumPy lists and dictionaries

Each list repeats one NumPy scalar object 1,024 times. Each dictionary maps
128 distinct keys to one scalar object. These fixtures do not measure
containers whose values are distinct scalar objects.

Every RSS worker constructs all 64 factory inputs, keeps the selected
fixture and discards the other 63 before collection and the pre-call
reading. Whole-process peak RSS and retained allocator state include
that setup, imports and identity checks. Peak RSS is not memory
allocated solely by serialization of the selected fixture.

### Allocation requests across thirty calls

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem 7b7e21c | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| 1,024 int64 scalars in a list | 457 | 487 | **307** |
| 1,024 float64 scalars in a list | 427 | 457 | **277** |
| 128 int64 scalars in a dict | 457 | 397 | **247** |
| 128 float64 scalars in a dict | 457 | 397 | **217** |

### Total requested memory across thirty calls, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem 7b7e21c | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| 1,024 int64 scalars in a list | 2.733 | 2.968 | **1.858** |
| 1,024 float64 scalars in a list | 1.413 | 1.649 | **0.919** |
| 128 int64 scalars in a dict | **0.431** | 0.444 | 0.449 |
| 128 float64 scalars in a dict | 0.383 | 0.397 | **0.214** |

### Peak tracked live memory, KiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem 7b7e21c | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| 1,024 int64 scalars in a list | 43.610 | 72.861 | **35.618** |
| 1,024 float64 scalars in a list | 27.610 | 43.861 | **19.618** |
| 128 int64 scalars in a dict | **9.985** | 14.736 | 11.618 |
| 128 float64 scalars in a dict | 9.985 | 13.111 | **7.618** |

### Whole-process peak RSS, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem 7b7e21c | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| 1,024 int64 scalars in a list | 35.145 | 35.734 | **34.531** |
| 1,024 float64 scalars in a list | 35.246 | 35.789 | **34.531** |
| 128 int64 scalars in a dict | 35.238 | 35.070 | **34.496** |
| 128 float64 scalars in a dict | 35.789 | 35.797 | **34.566** |

### RSS before calls, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem 7b7e21c | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| 1,024 int64 scalars in a list | 35.125 | 35.129 | **34.531** |
| 1,024 float64 scalars in a list | 35.133 | 35.789 | **34.531** |
| 128 int64 scalars in a dict | 35.219 | 35.070 | **34.496** |
| 128 float64 scalars in a dict | 35.211 | 35.797 | **34.566** |

### RSS after ten calls, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | jsonmodem 7b7e21c | jsonmodem 96318df | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| 1,024 int64 scalars in a list | 35.145 | 35.734 | **34.531** |
| 1,024 float64 scalars in a list | 35.246 | 35.789 | **34.531** |
| 128 int64 scalars in a dict | 35.238 | 35.070 | **34.496** |
| 128 float64 scalars in a dict | 35.789 | 35.797 | **34.566** |

KiB means 1,024 bytes; MiB means 1,048,576 bytes. RSS includes the whole
process. Allocator reuse and page accounting can retain RSS after objects
are freed. Raw startup, first-call and getrusage readings are in memory.json.

## Limits

- One Memray capture per workload and library does not establish variance.
- Inputs exist before tracking; results are discarded inside the thirty-call capture.
- Allocation requests include zero-size requests and full realloc sizes; free and unmap events are excluded.
- RSS workers do not import Memray and make ten calls with no warmup.
- The library is loaded at every RSS stage; first and final readings follow result disposal.
- There is no result-retained RSS reading. Peak RSS covers the whole process.
- The NumPy-container RSS workers construct all 64 factory inputs before retaining one; peak RSS and allocator state include that setup.
- Allocation requests, total requested bytes, peak tracked live bytes and RSS answer different questions.
- These memory observations do not measure execution time or isolate the effect of an individual source change.
