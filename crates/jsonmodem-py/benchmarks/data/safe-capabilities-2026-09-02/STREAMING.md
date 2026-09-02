# Streaming benchmark latency

All timings are absolute microseconds (us) per complete call, not per token or chunk.
A streaming call creates a parser, feeds every chunk, finishes the stream and handles
the results as described below. The whole-document reference parses one complete input.

PR #6 is the previous jsonmodem implementation. Rebuilt uses the same source
compiled again. Earlier is the first intermediate implementation measured
during this change. Selected is runtime revision `7b7e21c`, measured before the
later decimal, Unicode, tuple, and NumPy changes. Runtime revisions and binary
hashes are in streaming.json. Other libraries are named explicitly in each table.

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

| Input | PR #6 | Rebuilt | Earlier | Selected |
| --- | ---: | ---: | ---: | ---: |
| Small integers | 266.431 | **263.956** | 270.074 | 273.395 |
| Wide object | 1,699.676 | **1,694.381** | 1,761.534 | 1,711.283 |
| Long object keys | 886.739 | **885.784** | 907.830 | 945.406 |
| Nested strings | 7,512.479 | 7,467.510 | **7,436.533** | 7,449.187 |

#### Retained events

All events are collected in a list and kept through stream completion.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | PR #6 | Rebuilt | Earlier | Selected |
| --- | ---: | ---: | ---: | ---: |
| Small integers | 280.047 | 277.824 | **272.436** | 277.040 |
| Wide object | 1,694.133 | **1,649.413** | 1,677.151 | 1,743.624 |
| Long object keys | 977.504 | **955.044** | 986.540 | 1,024.472 |
| Nested strings | 11,338.645 | 10,131.387 | **7,658.103** | 8,696.991 |

### `JsonModemEvents(track_paths=True)`

Events include JSON paths.

#### Consumed events

Events are counted as they arrive; no result list is kept.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | Earlier | Selected |
| --- | ---: | ---: |
| Small integers | **261.612** | 271.675 |
| Wide object | 1,713.156 | **1,701.595** |
| Long object keys | **919.468** | 947.244 |
| Nested strings | **7,378.864** | 7,749.849 |

#### Retained events

All events are collected in a list and kept through stream completion.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | Earlier | Selected |
| --- | ---: | ---: |
| Small integers | 272.749 | **268.714** |
| Wide object | 1,722.912 | **1,670.280** |
| Long object keys | **989.351** | 1,021.023 |
| Nested strings | 7,849.240 | **7,757.899** |

### `JsonModemEvents()`

Events omit JSON paths.

#### Consumed events

Events are counted as they arrive; no result list is kept.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | Earlier | Selected |
| --- | ---: | ---: |
| Small integers | **182.916** | 199.081 |
| Wide object | **1,226.078** | 1,285.016 |
| Long object keys | **684.534** | 691.192 |
| Nested strings | **1,030.543** | 1,143.084 |

#### Retained events

All events are collected in a list and kept through stream completion.

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | Earlier | Selected |
| --- | ---: | ---: |
| Small integers | **169.755** | 187.487 |
| Wide object | **1,200.720** | 1,220.386 |
| Long object keys | **729.034** | 741.809 |
| Nested strings | **1,092.815** | 1,204.673 |

## Numeric events

Chunks end after complete number tokens. Each call consumes every event and
counts the numbers; it does not construct an array snapshot for each prefix.

### `JsonModem()`: consumed number events

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | PR #6 | Rebuilt | Earlier | Selected |
| --- | ---: | ---: | ---: | ---: |
| Small integers | 287.741 | 286.390 | **279.178** | 291.736 |
| Signed 64-bit integers | 361.436 | 360.906 | **351.050** | 372.563 |
| Unsigned 64-bit integers | 364.969 | 362.945 | **358.437** | 371.986 |
| Floating-point numbers | 383.975 | 389.397 | **373.290** | 381.131 |
| Mixed integers and floats | 388.951 | 401.507 | **370.820** | 386.633 |
| 200-bit integers | 727.366 | **674.950** | 687.692 | 690.855 |

### `JsonModem(byte_views=True)`: consumed number events

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | PR #6 | Rebuilt | Earlier | Selected |
| --- | ---: | ---: | ---: | ---: |
| Small integers | 354.003 | 357.826 | **348.660** | 359.424 |
| Signed 64-bit integers | **408.283** | 429.918 | 422.736 | 429.489 |
| Unsigned 64-bit integers | 421.159 | **420.029** | 421.615 | 428.429 |
| Floating-point numbers | 454.577 | 461.863 | **448.227** | 456.662 |
| Mixed integers and floats | 447.602 | 457.148 | **445.448** | 458.255 |
| 200-bit integers | 721.273 | **713.903** | 725.374 | 737.512 |

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

| Input | PR #6 | jiter 0.16.0 |
| --- | ---: | ---: |
| Small integers | 420.423 | **256.392** |
| Signed 64-bit integers | **1,852.477** | 3,343.011 |
| Unsigned 64-bit integers | **2,078.452** | 3,830.352 |
| Floating-point numbers | 1,236.238 | **1,125.680** |
| Mixed integers and floats | **1,595.586** | 2,264.294 |
| 200-bit integers | **17,096.813** | 18,345.951 |

### jsonmodem PR #6 rebuilt and jiter 0.16.0

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | Rebuilt | jiter 0.16.0 |
| --- | ---: | ---: |
| Small integers | 427.073 | **268.038** |
| Signed 64-bit integers | **1,857.310** | 3,299.716 |
| Unsigned 64-bit integers | **2,066.420** | 3,821.549 |
| Floating-point numbers | 1,229.596 | **1,116.666** |
| Mixed integers and floats | **1,593.006** | 2,231.543 |
| 200-bit integers | **16,618.046** | 18,269.556 |

### jsonmodem earlier combination and jiter 0.16.0

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | Earlier | jiter 0.16.0 |
| --- | ---: | ---: |
| Small integers | 421.468 | **258.178** |
| Signed 64-bit integers | **1,855.420** | 3,314.636 |
| Unsigned 64-bit integers | **2,111.798** | 3,805.727 |
| Floating-point numbers | 1,231.269 | **1,129.278** |
| Mixed integers and floats | **1,606.379** | 2,268.907 |
| 200-bit integers | **17,099.007** | 18,644.779 |

### jsonmodem selected build and jiter 0.16.0

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Input | Selected | jiter 0.16.0 |
| --- | ---: | ---: |
| Small integers | 426.222 | **262.748** |
| Signed 64-bit integers | **1,843.100** | 3,324.992 |
| Unsigned 64-bit integers | **2,033.516** | 3,860.631 |
| Floating-point numbers | 1,223.866 | **1,127.544** |
| Mixed integers and floats | **1,599.226** | 2,247.588 |
| 200-bit integers | **16,951.013** | 18,198.732 |

## Whole-document reference: orjson 3.11.9

Each call runs `orjson.loads()` once on the already complete document and
discards the result. It does not produce events or every intermediate prefix,
so this table is not ranked against the streaming APIs.

Microseconds (us) per complete call. Lower is better. Different work from the streaming APIs; no cross-API ranking.

| Input | orjson 3.11.9 |
| --- | ---: |
| Small integers | 16.982 |
| Wide object | 440.057 |
| Long object keys | 358.636 |
| Nested strings | 89.796 |

## Rust streaming APIs

Each API consumes its events or value updates without retaining them. It does
not create Python objects. Each row uses the same medium document and the
benchmark's requested chunk count; actual chunk counts are in the public JSON.
These tables use the five Criterion process medians described above.

### `JsonModem`: consumed results

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Requested chunks | PR #6 Rust core | Earlier Rust core | Selected Rust core |
| --- | ---: | ---: | ---: |
| 100 | **29.862** | 33.148 | 30.782 |
| 1,000 | **64.356** | 76.868 | 68.930 |
| 5,000 | **143.232** | 172.877 | 157.203 |

### `JsonModemBuffers`: consumed results

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Requested chunks | PR #6 Rust core | Earlier Rust core | Selected Rust core |
| --- | ---: | ---: | ---: |
| 100 | 42.582 | **40.537** | 43.020 |
| 1,000 | 86.416 | **85.119** | 91.588 |
| 5,000 | **174.111** | 179.582 | 181.299 |

### `JsonModemValues`: consumed results

Microseconds (us) per complete call. Lower is better. Bold marks the lowest latency in each row; exact ties are all bold.

| Requested chunks | PR #6 Rust core | Earlier Rust core | Selected Rust core |
| --- | ---: | ---: | ---: |
| 100 | 42.952 | **40.423** | 43.021 |
| 1,000 | **85.259** | 87.977 | 88.321 |
| 5,000 | **169.698** | 179.278 | 179.155 |
