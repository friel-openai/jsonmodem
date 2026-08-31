# Date/time: original control

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

Complete dumps latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 226.397 | 202.074 | **84.364** | 85.316 |
| `dataclass_dates` | 257.160 | 239.053 | **188.997** | 190.910 |
| `date_1024` | 44.547 | 40.039 | **17.881** | 18.331 |
| `date_1024_options` | 45.026 | 40.323 | **18.267** | 18.440 |
| `date_16` | 1.394 | 1.307 | **0.417** | 0.418 |
| `date_scalar` | 0.616 | 0.629 | 0.189 | **0.187** |
| `datetime_fixed_offset_1024` | 94.342 | **91.832** | 109.294 | 108.754 |
| `datetime_fixed_offset_16` | 2.355 | 2.369 | **1.821** | 1.830 |
| `datetime_fixed_offset_scalar` | 0.708 | 0.698 | **0.282** | 0.286 |
| `datetime_naive_1024` | 59.139 | 56.105 | **29.605** | 29.715 |
| `datetime_naive_1024_naive_utc` | 60.983 | 58.417 | 32.380 | **31.330** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 53.524 | 50.563 | **25.211** | 25.580 |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 53.902 | 50.372 | **25.106** | 25.322 |
| `datetime_naive_1024_naive_utc_z` | 58.949 | 56.877 | **31.160** | 31.469 |
| `datetime_naive_1024_omit_microseconds` | 52.798 | 49.682 | 23.107 | **22.780** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 52.877 | 50.201 | **22.790** | 23.125 |
| `datetime_naive_1024_utc_z` | 58.900 | 56.723 | **29.537** | 29.790 |
| `datetime_naive_1024_zero_microseconds` | 52.384 | 49.860 | **23.301** | 23.783 |
| `datetime_naive_16` | 1.737 | 1.704 | **0.614** | 0.622 |
| `datetime_naive_scalar` | 0.655 | 0.647 | **0.196** | 0.197 |
| `datetime_named_zero_offset_1024` | 90.614 | **86.491** | 101.282 | 100.556 |
| `datetime_negative_offset_1024` | 95.072 | **92.723** | 109.329 | 108.899 |
| `datetime_passthrough` | 924.624 | 919.512 | **665.366** | 665.457 |
| `datetime_seconds_offset_1024` | 94.001 | **92.460** | 108.570 | 108.806 |
| `datetime_subclass` | 759.917 | 754.386 | 702.153 | **699.086** |
| `datetime_utc_1024` | 66.648 | **65.830** | 101.254 | 100.893 |
| `datetime_utc_1024_omit_microseconds` | 58.836 | **58.327** | 91.828 | 92.214 |
| `datetime_utc_1024_omit_microseconds_utc_z` | 59.147 | **58.106** | 91.234 | 91.949 |
| `datetime_utc_1024_utc_z` | 64.954 | **64.519** | 98.666 | 100.733 |
| `datetime_utc_1024_zero_microseconds` | 58.913 | **58.572** | 92.397 | 91.750 |
| `datetime_utc_16` | 1.878 | 1.841 | 1.738 | **1.723** |
| `datetime_utc_scalar` | 0.645 | 0.651 | **0.277** | 0.279 |
| `dict_control` | 0.320 | 0.268 | 0.233 | **0.229** |
| `list_control` | 11.091 | 10.874 | **4.410** | 4.411 |
| `string_control` | 0.180 | 0.169 | 0.175 | **0.169** |
| `time_1024_omit_microseconds` | 56.077 | 50.320 | **19.706** | 19.769 |
| `time_1024_zero_microseconds` | 55.673 | 50.139 | **19.727** | 19.881 |
| `time_scalar` | 0.628 | 0.633 | **0.177** | 0.194 |
| `uuid_list_control` | 907.954 | 80.079 | **44.929** | 45.854 |
| `uuid_scalar_control` | 1.654 | 0.648 | **0.230** | 0.231 |

## Different output bytes

These three cases are excluded from the orjson geometric mean.
The two jsonmodem columns match each other; the two orjson columns form a separate group.

Complete dumps latency (us). Bold compares only columns with equal output bytes. Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 177.577 | **167.791** | 148.350 | **147.792** |
| `time_1024` | 66.852 | **61.830** | 26.850 | **26.755** |
| `time_16` | 1.859 | **1.764** | 0.505 | **0.503** |
