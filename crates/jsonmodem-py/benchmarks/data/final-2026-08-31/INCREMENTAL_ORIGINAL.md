# Incremental APIs: original control

[Summary](PERFORMANCE_FINAL.md). These results do not enter complete-document scores.

Events: microseconds per complete stream, including event materialization. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `small_integers` | 284.333 | **283.209** |
| `wide_signed` | 357.417 | **356.754** |
| `wide_unsigned` | **365.737** | 365.756 |
| `floats` | 380.394 | **371.844** |
| `mixed_numbers` | **381.151** | 382.652 |
| `large_integers` | **676.849** | 689.206 |

Byte-view events: microseconds per complete stream, including event materialization. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `small_integers` | **342.269** | 354.455 |
| `wide_signed` | 423.049 | **421.297** |
| `wide_unsigned` | **411.507** | 429.675 |
| `floats` | **441.909** | 455.084 |
| `mixed_numbers` | **446.995** | 449.238 |
| `large_integers` | 729.555 | **708.488** |

All cumulative array prefixes, including materialization (us). Jiter includes constructing contiguous prefix bytes. Lower is better.

| Case | Original values | Final values | jiter in original workers | jiter in final workers |
| --- | ---: | ---: | ---: | ---: |
| `small_integers` | 417.315 | 416.772 | 249.310 | **249.310** |
| `wide_signed` | 1,880.640 | **1,871.400** | 3,343.333 | 3,339.348 |
| `wide_unsigned` | **2,051.635** | 2,091.556 | 3,823.340 | 3,851.115 |
| `floats` | 1,254.203 | 1,226.730 | 1,125.828 | **1,125.669** |
| `mixed_numbers` | **1,583.586** | 1,585.668 | 2,243.452 | 2,242.698 |
| `large_integers` | 17,004.925 | **16,697.523** | 18,465.825 | 18,555.466 |

## String buffers

Short strings have length 4 and 512-byte chunks; long strings have length 256 and 4,096-byte chunks.
The runner imports Memray before timing but does not track allocations during timing.
It retains process medians, not individual batches, and deletes its separate allocation captures.

Short strings: microseconds per complete stream. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `bytes` | 333.458 | **307.740** |
| `byte_views_bytes` | **470.481** | 477.769 |
| `byte_views_exporter` | **478.821** | 488.442 |

Long strings: microseconds per complete stream. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `bytes` | 413.488 | **401.355** |
| `byte_views_bytes` | **609.390** | 633.069 |
| `byte_views_exporter` | **678.224** | 691.520 |

Reported allocation requests per stream (not independently recounted). One allocation worker per build and variant. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `short/bytes` | **2,921.460** | **2,921.460** |
| `short/byte_views_bytes` | **4,111.070** | **4,111.070** |
| `short/byte_views_exporter` | **4,291.070** | **4,291.070** |
| `long/bytes` | **3,238.100** | **3,238.100** |
| `long/byte_views_bytes` | **5,820.070** | **5,820.070** |
| `long/byte_views_exporter` | **6,600.070** | **6,600.070** |

Reported peak tracked memory during 100 streams (KiB; not RSS). One allocation worker per build and variant. Lower is better.

| Case | Original | Final |
| --- | ---: | ---: |
| `short/bytes` | **10.324** | **10.324** |
| `short/byte_views_bytes` | **2,834.440** | **2,834.440** |
| `short/byte_views_exporter` | **2,835.402** | **2,835.402** |
| `long/bytes` | **7.347** | **7.347** |
| `long/byte_views_bytes` | **5,428.812** | **5,428.812** |
| `long/byte_views_exporter` | **5,433.273** | **5,433.273** |
