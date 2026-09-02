# Complete-call memory comparisons

PR #6 runtime source: `b889f4cd0323b2f60729eb61c35429fbe611fd47`.
Selected runtime source: `7b7e21c3bd49d22c0964c4a30be16b5367160caf`.

The runtime revisions identify the measured builds. Any later publication
revision is recorded separately in memory.json, not substituted for a measured revision.

Displayed table values are rounded. Bold uses unrounded counters;
memory.json retains the exact counts.

Each Memray workload has one capture of thirty calls after ten warmup calls
and garbage collection. Inputs exist before capture; returned results are
released inside capture. Memray 1.20.0 tracks native and Python allocator
requests. Totals include the capture loop; these are not repeated estimates or RSS.

An "array view" is `memoryview(array.array("B", document))`, backed by
a byte array, not a NumPy view.

## Allocation requests across thirty calls

Lower is better. Bold marks the lowest value in each row.

| Workload | PR #6 | Selected build | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | 135,842 | 138,169 | **134,942** |
| Encode a small object | 127 | 127 | **97** |
| Encode 1,000 records | 397 | 397 | **277** |
| Encode a long string | **97** | **97** | 127 |
| Encode 1,000 records, sorted keys | 30,457 | 30,457 | **30,337** |
| Encode 1,000 fragments | 307 | 307 | **217** |
| Encode 1,000 two-field dataclasses | 457 | 457 | **247** |
| Encode a 25,000 × 4 float32 array (100,000 values) | **1,147** | **1,147** | 751,027 |
| Large output followed by a callback | 727 | 757 | **487** |
| Decode a small object from an array view | 277 | 337 | **247** |
| Decode a small object | **247** | 307 | **247** |
| Decode 1,000 records from an array view | 135,888 | 138,211 | **134,958** |
| Decode a long string from an array view | **127** | **127** | **127** |
| Decode a long string | **97** | **97** | 127 |

## Total requested memory across thirty calls, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | PR #6 | Selected build | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | **9.551** | 10.040 | 26.104 |
| Encode a small object | **0.012** | **0.012** | 0.032 |
| Encode 1,000 records | 5.279 | 5.279 | **3.729** |
| Encode a long string | **4.105** | **4.105** | 60.033 |
| Encode 1,000 records, sorted keys | 7.114 | 7.114 | **5.794** |
| Encode 1,000 fragments | 1.334 | 1.334 | **0.915** |
| Encode 1,000 two-field dataclasses | 2.928 | 2.935 | **1.854** |
| Encode a 25,000 × 4 float32 array (100,000 values) | **93.636** | 93.637 | 221.431 |
| Large output followed by a callback | 2,508.822 | 3,469.526 | **1,918.175** |
| Decode a small object from an array view | **0.012** | 0.016 | 0.125 |
| Decode a small object | **0.010** | 0.013 | 0.125 |
| Decode 1,000 records from an array view | **11.083** | 11.572 | 26.105 |
| Decode a long string from an array view | **8.207** | **8.207** | 53.441 |
| Decode a long string | **4.105** | **4.105** | 53.441 |

## Peak tracked live memory, KiB

Lower is better. Bold marks the lowest value in each row.

| Workload | PR #6 | Selected build | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | **283.059** | 301.055 | 907.100 |
| Encode a small object | **0.379** | **0.379** | 1.103 |
| Encode 1,000 records | 116.405 | 116.405 | **64.103** |
| Encode a long string | **140.104** | **140.104** | 2,048.103 |
| Encode 1,000 records, sorted keys | 119.944 | 119.944 | **67.681** |
| Encode 1,000 fragments | 29.744 | 29.744 | **16.103** |
| Encode 1,000 two-field dataclasses | 60.311 | 40.017 | **32.103** |
| Encode a 25,000 × 4 float32 array (100,000 values) | **2,238.349** | 2,238.356 | 3,978.384 |
| Large output followed by a callback | 52,810.304 | 32,834.860 | **32,771.751** |
| Decode a small object from an array view | **0.381** | 3.896 | 4.234 |
| Decode a small object | **0.322** | 3.838 | 4.234 |
| Decode 1,000 records from an array view | **335.331** | 353.577 | 907.100 |
| Decode a long string from an array view | **280.113** | **280.113** | 1,824.079 |
| Decode a long string | **140.110** | **140.110** | 1,824.079 |

# Process memory

Each cell is the median of three fresh processes, each making ten calls
after garbage collection. These workers do not import Memray. The library
is loaded at every reported stage; inputs exist before the pre-call reading.
Returned results are discarded before the first and final readings. There
is no result-retained RSS reading. Peak RSS includes temporary memory
during calls and all other memory in the process.

## Whole-process peak RSS, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | PR #6 | Selected build | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | 21.262 | 21.375 | **20.238** |
| Decode 100,000 records | **57.426** | 57.531 | 75.555 |
| Encode 1,000 records | 21.293 | 21.266 | **20.156** |
| Encode 1,000 fragments | 21.273 | 21.371 | **19.938** |
| Encode 1,000 two-field dataclasses | 21.254 | 21.328 | **20.254** |
| Encode a 25,000 × 4 float32 array (100,000 values) | **37.461** | 37.707 | 37.648 |
| Large output followed by a callback | 62.312 | 58.699 | **40.996** |

## RSS before calls, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | PR #6 | Selected build | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | 20.609 | 20.723 | **19.926** |
| Decode 100,000 records | 26.117 | 26.090 | **25.160** |
| Encode 1,000 records | 20.875 | 20.898 | **20.156** |
| Encode 1,000 fragments | 20.648 | 20.719 | **19.938** |
| Encode 1,000 two-field dataclasses | 20.629 | 20.703 | **19.938** |
| Encode a 25,000 × 4 float32 array (100,000 values) | 35.234 | 35.105 | **34.438** |
| Large output followed by a callback | 20.578 | 20.555 | **20.008** |

## RSS after ten calls, MiB

Lower is better. Bold marks the lowest value in each row.

| Workload | PR #6 | Selected build | orjson 3.11.9 |
| --- | ---: | ---: | ---: |
| Decode 1,000 records | 20.941 | 21.059 | **20.238** |
| Decode 100,000 records | 29.965 | 30.117 | **29.141** |
| Encode 1,000 records | 20.875 | 20.898 | **20.156** |
| Encode 1,000 fragments | 20.648 | 20.719 | **19.938** |
| Encode 1,000 two-field dataclasses | 20.973 | 21.016 | **20.254** |
| Encode a 25,000 × 4 float32 array (100,000 values) | **35.660** | 35.906 | 37.648 |
| Large output followed by a callback | 41.172 | 38.684 | **21.016** |

KiB means 1,024 bytes; MiB means 1,048,576 bytes. Exact raw counters,
including startup, first-call and getrusage readings, remain in memory.json.
Allocator reuse and page accounting can retain RSS after objects are freed.

## Limits

- One Memray capture per workload and library does not establish variance.
- Inputs exist before capture; results are discarded inside the thirty-call capture.
- Allocation requests include zero-size requests and full realloc sizes; free and unmap events are excluded.
- RSS workers do not import Memray. The library is loaded at every reported stage.
- There is no result-retained RSS reading; first and final readings follow result disposal.
- Peak RSS covers the whole process, including temporary memory during calls.
- Allocation requests, total requested bytes, peak tracked live bytes and RSS answer different questions.
- Artifact integrity does not validate discarded serializer outputs; correctness requires separate release tests and benchmark preflight.
