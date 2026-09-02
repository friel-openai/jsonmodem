# Streaming benchmark latency

The selected build is runtime revision `96318df`, including the shared
long-decimal correction, checked local Unicode conversions, revised tuple
setter, and dedicated NumPy container writer. The earlier measurements of
`7b7e21c` remain in the separate historical report.

All timings are absolute microseconds (us) per complete call, not per token or chunk.
A streaming call creates a parser, feeds every chunk, finishes the stream and handles
the results as described below. The whole-document reference parses one complete input.

In the supplied report, `jsonmodem PR #6` is the previous published implementation.
`jsonmodem PR #6 rebuilt` is the same source compiled again.
`jsonmodem earlier combination` is the first intermediate implementation measured
during this change. `jsonmodem selected build` is the implementation chosen for that
report. Runtime revisions and binary hashes are in the accompanying public JSON.

## How the numbers are summarized

For each Python case and build, five separate processes each record three timing
samples. Each sample divides the elapsed time for repeated complete calls by the
number of calls. Each table takes the median of the three samples in each process,
then the median of those five process medians. It does not pool all 15 samples.

The Rust tables instead take the median of five process medians reported by Criterion,
the Rust benchmark harness. Those are not raw Criterion iteration samples.

Printed values are rounded to three decimal places; very small values use scientific
notation. Bold uses the unrounded medians. The accompanying public JSON preserves
all exported samples, call counts, input sizes, chunk counts and build hashes.

## Python events

Each mode and retention policy has a separate table. Only builds running the same
API and retaining the same output compete within a row.

### `JsonModem()`

Events include JSON paths.

#### Consumed events

Events are counted as they arrive; no result list is kept.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem PR #6 | jsonmodem PR #6 rebuilt | jsonmodem earlier combination | jsonmodem selected build |
| --- | ---: | ---: | ---: | ---: |
| Small integers | 265.559 | 264.811 | **261.643** | 272.640 |
| Wide object | 1,698.395 | 1,674.625 | 1,700.707 | **1,674.075** |
| Long object keys | 894.111 | **880.418** | 916.639 | 926.350 |
| Nested strings | 7,434.704 | 7,280.713 | 7,309.308 | **7,263.556** |

#### Retained events

All events are collected in a list and kept through stream completion.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem PR #6 | jsonmodem PR #6 rebuilt | jsonmodem earlier combination | jsonmodem selected build |
| --- | ---: | ---: | ---: | ---: |
| Small integers | 280.489 | 277.772 | **268.734** | 280.550 |
| Wide object | 1,815.531 | **1,660.993** | 1,686.112 | 1,797.394 |
| Long object keys | 965.020 | **964.451** | 993.466 | 993.944 |
| Nested strings | 12,165.428 | 11,622.059 | **8,560.511** | 8,705.141 |

### `JsonModemEvents(track_paths=True)`

Events include JSON paths.

#### Consumed events

Events are counted as they arrive; no result list is kept.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem earlier combination | jsonmodem selected build |
| --- | ---: | ---: |
| Small integers | **258.071** | 273.363 |
| Wide object | **1,715.611** | 1,718.786 |
| Long object keys | 922.939 | **922.572** |
| Nested strings | 7,448.063 | **7,264.609** |

#### Retained events

All events are collected in a list and kept through stream completion.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem earlier combination | jsonmodem selected build |
| --- | ---: | ---: |
| Small integers | **270.404** | 277.188 |
| Wide object | **1,726.049** | 1,777.480 |
| Long object keys | 991.979 | **984.585** |
| Nested strings | 12,389.401 | **8,712.683** |

### `JsonModemEvents()`

Events omit JSON paths.

#### Consumed events

Events are counted as they arrive; no result list is kept.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem earlier combination | jsonmodem selected build |
| --- | ---: | ---: |
| Small integers | **183.048** | 190.486 |
| Wide object | **1,246.178** | 1,295.636 |
| Long object keys | **682.352** | 687.597 |
| Nested strings | **1,017.300** | 1,097.106 |

#### Retained events

All events are collected in a list and kept through stream completion.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem earlier combination | jsonmodem selected build |
| --- | ---: | ---: |
| Small integers | **170.542** | 180.320 |
| Wide object | **1,194.238** | 1,270.109 |
| Long object keys | **728.371** | 736.629 |
| Nested strings | **1,100.323** | 1,133.574 |

## Numeric events

Chunks end after complete number tokens. Each call consumes every event and
counts the numbers; it does not construct an array snapshot for each prefix.

### `JsonModem()`: consumed number events

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem PR #6 | jsonmodem PR #6 rebuilt | jsonmodem earlier combination | jsonmodem selected build |
| --- | ---: | ---: | ---: | ---: |
| Small integers | 292.070 | 290.852 | **279.195** | 290.273 |
| Signed 64-bit integers | 358.643 | 358.870 | **350.461** | 360.641 |
| Unsigned 64-bit integers | 365.932 | 362.677 | **360.326** | 373.643 |
| Floating-point numbers | 385.116 | 388.056 | **371.201** | 381.561 |
| Mixed integers and floats | 389.900 | 393.004 | **370.308** | 382.904 |
| 200-bit integers | 687.010 | 679.289 | 687.344 | **656.728** |

### `JsonModem(byte_views=True)`: consumed number events

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem PR #6 | jsonmodem PR #6 rebuilt | jsonmodem earlier combination | jsonmodem selected build |
| --- | ---: | ---: | ---: | ---: |
| Small integers | 353.535 | 351.796 | **350.241** | 351.011 |
| Signed 64-bit integers | 422.923 | 422.787 | **419.387** | 427.217 |
| Unsigned 64-bit integers | 425.788 | 422.897 | **419.405** | 429.345 |
| Floating-point numbers | 448.798 | 464.930 | **440.752** | 450.431 |
| Mixed integers and floats | 446.507 | 455.647 | **442.470** | 451.981 |
| 200-bit integers | 710.780 | **707.900** | 720.693 | 731.175 |

## Cumulative array prefixes

Each call constructs a Python array value after every chunk. A `JsonModemValues`
parser uses `view().snapshot()`. jiter uses `from_json(partial_mode=True)`
on each accumulated prefix, including the work of creating contiguous prefix bytes.
These rows compare the same sequence of prefix values, not event production.

Each table pairs one jsonmodem build with the jiter measurements taken in the
same processes. All four tables use jiter 0.16.0. Its four measurement sets are
kept separate; they are not different jiter builds and are not pooled.

### jsonmodem PR #6 and jiter 0.16.0

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem PR #6 | jiter 0.16.0 |
| --- | ---: | ---: |
| Small integers | 418.209 | **252.104** |
| Signed 64-bit integers | **1,857.738** | 3,322.765 |
| Unsigned 64-bit integers | **2,076.234** | 3,824.059 |
| Floating-point numbers | 1,230.243 | **1,124.721** |
| Mixed integers and floats | **1,597.170** | 2,233.180 |
| 200-bit integers | **16,610.814** | 18,279.053 |

### jsonmodem PR #6 rebuilt and jiter 0.16.0

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem PR #6 rebuilt | jiter 0.16.0 |
| --- | ---: | ---: |
| Small integers | 429.455 | **259.515** |
| Signed 64-bit integers | **1,849.050** | 3,269.156 |
| Unsigned 64-bit integers | **2,058.989** | 3,858.437 |
| Floating-point numbers | 1,260.001 | **1,135.298** |
| Mixed integers and floats | **1,593.975** | 2,251.538 |
| 200-bit integers | **16,664.132** | 18,339.449 |

### jsonmodem earlier combination and jiter 0.16.0

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem earlier combination | jiter 0.16.0 |
| --- | ---: | ---: |
| Small integers | 427.962 | **266.231** |
| Signed 64-bit integers | **1,863.250** | 3,323.334 |
| Unsigned 64-bit integers | **2,102.424** | 3,853.471 |
| Floating-point numbers | 1,239.456 | **1,132.731** |
| Mixed integers and floats | **1,582.076** | 2,231.557 |
| 200-bit integers | **16,600.580** | 18,180.551 |

### jsonmodem selected build and jiter 0.16.0

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | jsonmodem selected build | jiter 0.16.0 |
| --- | ---: | ---: |
| Small integers | 428.736 | **251.240** |
| Signed 64-bit integers | **1,842.531** | 3,315.375 |
| Unsigned 64-bit integers | **2,148.579** | 3,854.508 |
| Floating-point numbers | 1,257.391 | **1,132.227** |
| Mixed integers and floats | **1,619.734** | 2,245.410 |
| 200-bit integers | **16,941.716** | 18,160.834 |

## Whole-document reference: orjson 3.11.9

Each call runs `orjson.loads()` once on the already complete document and
discards the result. It does not produce events or every intermediate prefix,
so this table is not ranked against the streaming APIs.

Microseconds (us) per complete call. Lower is better. Different work from the streaming APIs; no cross-API ranking.

| Input | orjson 3.11.9 |
| --- | ---: |
| Small integers | 16.934 |
| Wide object | 430.082 |
| Long object keys | 356.691 |
| Nested strings | 90.577 |

## Rust streaming APIs

Each API consumes its events or value updates without retaining them. It does
not create Python objects. Each row uses the same medium document and the
benchmark's requested chunk count; actual chunk counts are in the public JSON.
These tables use the five Criterion process medians described above.

### `JsonModem`: consumed results

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Requested chunks | jsonmodem PR #6 Rust core | jsonmodem earlier Rust core | jsonmodem selected Rust core |
| --- | ---: | ---: | ---: |
| 100 | **30.177** | 32.897 | 31.989 |
| 1,000 | **64.450** | 76.996 | 77.001 |
| 5,000 | **142.372** | 172.819 | 181.895 |

### `JsonModemBuffers`: consumed results

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Requested chunks | jsonmodem PR #6 Rust core | jsonmodem earlier Rust core | jsonmodem selected Rust core |
| --- | ---: | ---: | ---: |
| 100 | **39.440** | 42.635 | 43.831 |
| 1,000 | **83.482** | 89.079 | 92.304 |
| 5,000 | **173.689** | 179.881 | 180.986 |

### `JsonModemValues`: consumed results

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Requested chunks | jsonmodem PR #6 Rust core | jsonmodem earlier Rust core | jsonmodem selected Rust core |
| --- | ---: | ---: | ---: |
| 100 | **40.648** | 42.984 | 43.595 |
| 1,000 | **83.231** | 88.642 | 89.434 |
| 5,000 | **167.531** | 177.868 | 179.597 |
