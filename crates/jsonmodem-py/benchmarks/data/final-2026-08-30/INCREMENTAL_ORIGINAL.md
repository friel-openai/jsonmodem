# Incremental APIs: original control

Original is the existing PR #3 build (`b7fe329`).
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

| Case | Original | Final |
| --- | ---: | ---: |
| `small_integers` | 296.197 | **285.850** |
| `wide_signed` | 361.180 | **358.263** |
| `wide_unsigned` | 373.316 | **360.115** |
| `floats` | **377.103** | 380.178 |
| `mixed_numbers` | 385.045 | **381.634** |
| `large_integers` | **672.997** | 677.252 |

Byte-view events: microseconds per complete stream, including event materialization. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `small_integers` | 348.370 | **343.837** |
| `wide_signed` | **424.537** | 424.682 |
| `wide_unsigned` | 424.200 | **412.739** |
| `floats` | 456.135 | **439.175** |
| `mixed_numbers` | 455.240 | **446.675** |
| `large_integers` | **720.132** | 726.183 |

All cumulative array prefixes, including materialization (us). Jiter includes constructing contiguous prefix bytes. Lower is better.

| Case | Original values | Final values | jiter in original workers | jiter in final workers |
| --- | ---: | ---: | ---: | ---: |
| `small_integers` | 426.614 | 419.741 | 268.031 | **252.228** |
| `wide_signed` | **1,834.355** | 1,868.730 | 3,337.431 | 3,299.927 |
| `wide_unsigned` | 2,094.171 | **2,058.072** | 3,813.741 | 3,784.701 |
| `floats` | 1,247.260 | 1,257.047 | **1,125.447** | 1,125.743 |
| `mixed_numbers` | 1,591.951 | **1,582.030** | 2,251.908 | 2,226.703 |
| `large_integers` | **16,841.319** | 16,863.294 | 18,542.882 | 18,263.018 |

## String buffers

Short strings have length 4 and 512-byte chunks; long strings have length 256 and 4,096-byte chunks.
The runner imports Memray before timing but does not track allocations during timing.
It retains process medians, not individual batches, and deletes its separate allocation captures.

Short strings: microseconds per complete stream. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `bytes` | **332.946** | 333.238 |
| `byte_views_bytes` | 477.470 | **469.925** |
| `byte_views_exporter` | 488.428 | **478.537** |

Long strings: microseconds per complete stream. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `bytes` | 415.238 | **412.770** |
| `byte_views_bytes` | 621.588 | **610.035** |
| `byte_views_exporter` | 682.300 | **669.433** |

Reported allocation requests per stream (not independently recounted). One allocation worker per build and variant. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `short/bytes` | **2,921.460** | **2,921.460** |
| `short/byte_views_bytes` | **4,111.070** | **4,111.070** |
| `short/byte_views_exporter` | **4,291.070** | **4,291.070** |
| `long/bytes` | **3,238.100** | **3,238.100** |
| `long/byte_views_bytes` | **5,820.070** | **5,820.070** |
| `long/byte_views_exporter` | **6,600.070** | **6,600.070** |

Reported tracked peak per stream (KiB; not RSS). One allocation worker per build and variant. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `short/bytes` | **10.324** | **10.324** |
| `short/byte_views_bytes` | **2,834.440** | **2,834.440** |
| `short/byte_views_exporter` | **2,835.402** | **2,835.402** |
| `long/bytes` | **7.347** | **7.347** |
| `long/byte_views_bytes` | **5,428.812** | **5,428.812** |
| `long/byte_views_exporter` | **5,433.273** | **5,433.273** |
