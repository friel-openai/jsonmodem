# Incremental APIs: rebuilt control

Rebuilt is a new compilation of unchanged PR #3 source (`b7fe329`).
Final is the changed implementation (`b0f3190`).
Value snapshots are compared with jiter 0.16.0; orjson has no incremental
parser. See [definitions and methods](README.md).

Events measures `JsonModem.feed()` and `finish()`, including creating each
event's kind, path and value. Byte-view events uses the same parser with
`byte_views=True`. Values takes a `JsonModemValues.view().snapshot()` after
every chunk; jiter instead reparses the accumulated prefix. Numeric arrays
contain 1,024 values and chunks do not split number tokens.

[Summary](PERFORMANCE_FINAL.md). These results do not enter complete-document scores.

Events: microseconds per complete stream, including event materialization. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `small_integers` | 294.813 | **284.658** |
| `wide_signed` | 358.793 | **356.514** |
| `wide_unsigned` | 372.608 | **356.796** |
| `floats` | **374.032** | 380.615 |
| `mixed_numbers` | 383.283 | **379.849** |
| `large_integers` | **670.461** | 677.099 |

Byte-view events: microseconds per complete stream, including event materialization. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `small_integers` | **345.398** | 345.942 |
| `wide_signed` | **414.716** | 424.004 |
| `wide_unsigned` | **413.319** | 414.481 |
| `floats` | 450.459 | **438.688** |
| `mixed_numbers` | **445.816** | 447.577 |
| `large_integers` | **718.074** | 728.932 |

All cumulative array prefixes, including materialization (us). Jiter includes constructing contiguous prefix bytes. Lower is better.

| Case | Rebuilt values | Final values | jiter in rebuilt workers | jiter in final workers |
| --- | ---: | ---: | ---: | ---: |
| `small_integers` | 426.829 | 418.939 | **249.686** | 249.783 |
| `wide_signed` | 1,870.857 | **1,865.504** | 3,295.379 | 3,311.189 |
| `wide_unsigned` | 2,079.269 | **2,052.182** | 3,849.365 | 3,792.531 |
| `floats` | 1,240.075 | 1,252.032 | **1,124.663** | 1,125.364 |
| `mixed_numbers` | 1,593.886 | **1,584.930** | 2,236.737 | 2,228.253 |
| `large_integers` | **16,819.378** | 16,965.517 | 18,259.870 | 18,230.024 |

## String buffers

Short strings have length 4 and 512-byte chunks; long strings have length 256 and 4,096-byte chunks.
The runner imports Memray before timing but does not track allocations during timing.
It retains process medians, not individual batches, and deletes its separate allocation captures.

Short strings: microseconds per complete stream. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `bytes` | **325.388** | 330.885 |
| `byte_views_bytes` | 472.135 | **467.207** |
| `byte_views_exporter` | 499.701 | **481.181** |

Long strings: microseconds per complete stream. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `bytes` | **407.385** | 413.797 |
| `byte_views_bytes` | 613.004 | **609.612** |
| `byte_views_exporter` | 678.731 | **673.573** |

Reported allocation requests per stream (not independently recounted). One allocation worker per build and variant. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `short/bytes` | **2,921.460** | **2,921.460** |
| `short/byte_views_bytes` | **4,111.070** | **4,111.070** |
| `short/byte_views_exporter` | **4,291.070** | **4,291.070** |
| `long/bytes` | **3,238.100** | **3,238.100** |
| `long/byte_views_bytes` | **5,820.070** | **5,820.070** |
| `long/byte_views_exporter` | **6,600.070** | **6,600.070** |

Reported tracked peak per stream (KiB; not RSS). One allocation worker per build and variant. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `short/bytes` | **10.324** | **10.324** |
| `short/byte_views_bytes` | **2,834.440** | **2,834.440** |
| `short/byte_views_exporter` | **2,835.402** | **2,835.402** |
| `long/bytes` | **7.347** | **7.347** |
| `long/byte_views_bytes` | **5,428.812** | **5,428.812** |
| `long/byte_views_exporter` | **5,433.273** | **5,433.273** |
