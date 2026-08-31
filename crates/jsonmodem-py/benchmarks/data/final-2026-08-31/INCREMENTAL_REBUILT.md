# Incremental APIs: rebuilt control

[Summary](PERFORMANCE_FINAL.md). These results do not enter complete-document scores.

Events: microseconds per complete stream, including event materialization. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `small_integers` | 288.160 | **287.941** |
| `wide_signed` | **358.120** | 361.968 |
| `wide_unsigned` | **360.111** | 367.124 |
| `floats` | **373.259** | 377.011 |
| `mixed_numbers` | **376.917** | 386.298 |
| `large_integers` | **680.408** | 685.605 |

Byte-view events: microseconds per complete stream, including event materialization. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `small_integers` | **342.072** | 349.059 |
| `wide_signed` | **423.249** | 424.227 |
| `wide_unsigned` | **415.461** | 423.118 |
| `floats` | **445.858** | 456.108 |
| `mixed_numbers` | **443.246** | 450.237 |
| `large_integers` | 727.747 | **708.875** |

All cumulative array prefixes, including materialization (us). Jiter includes constructing contiguous prefix bytes. Lower is better.

| Case | Rebuilt values | Final values | jiter in rebuilt workers | jiter in final workers |
| --- | ---: | ---: | ---: | ---: |
| `small_integers` | 417.906 | 416.252 | **257.976** | 259.258 |
| `wide_signed` | 1,875.456 | **1,874.335** | 3,345.095 | 3,351.874 |
| `wide_unsigned` | **2,045.274** | 2,081.002 | 3,802.986 | 3,826.500 |
| `floats` | 1,229.167 | 1,231.232 | **1,122.493** | 1,128.073 |
| `mixed_numbers` | **1,573.332** | 1,585.552 | 2,243.343 | 2,237.627 |
| `large_integers` | 16,999.863 | **16,942.748** | 18,486.470 | 18,238.185 |

## String buffers

Short strings have length 4 and 512-byte chunks; long strings have length 256 and 4,096-byte chunks.
The runner imports Memray before timing but does not track allocations during timing.
It retains process medians, not individual batches, and deletes its separate allocation captures.

Short strings: microseconds per complete stream. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `bytes` | **304.408** | 308.535 |
| `byte_views_bytes` | **467.861** | 478.339 |
| `byte_views_exporter` | 488.599 | **485.993** |

Long strings: microseconds per complete stream. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `bytes` | **399.986** | 404.377 |
| `byte_views_bytes` | **620.945** | 637.819 |
| `byte_views_exporter` | **679.533** | 699.459 |

Reported allocation requests per stream (not independently recounted). One allocation worker per build and variant. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `short/bytes` | **2,921.460** | **2,921.460** |
| `short/byte_views_bytes` | **4,111.070** | **4,111.070** |
| `short/byte_views_exporter` | **4,291.070** | **4,291.070** |
| `long/bytes` | **3,238.100** | **3,238.100** |
| `long/byte_views_bytes` | **5,820.070** | **5,820.070** |
| `long/byte_views_exporter` | **6,600.070** | **6,600.070** |

Reported peak tracked memory during 100 streams (KiB; not RSS). One allocation worker per build and variant. Lower is better.

| Case | Rebuilt | Final |
| --- | ---: | ---: |
| `short/bytes` | **10.324** | **10.324** |
| `short/byte_views_bytes` | **2,834.440** | **2,834.440** |
| `short/byte_views_exporter` | **2,835.402** | **2,835.402** |
| `long/bytes` | **7.347** | **7.347** |
| `long/byte_views_bytes` | **5,428.812** | **5,428.812** |
| `long/byte_views_exporter` | **5,433.273** | **5,433.273** |
