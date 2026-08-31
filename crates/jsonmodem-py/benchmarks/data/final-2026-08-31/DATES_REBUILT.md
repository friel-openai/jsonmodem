# Date/time: rebuilt control

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

Complete dumps latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 221.402 | 206.391 | **85.073** | 85.444 |
| `dataclass_dates` | 254.666 | 238.623 | 191.489 | **186.995** |
| `date_1024` | 44.833 | 40.007 | **18.188** | 18.241 |
| `date_1024_options` | 45.141 | 40.582 | **18.231** | 18.337 |
| `date_16` | 1.387 | 1.305 | 0.443 | **0.416** |
| `date_scalar` | 0.617 | 0.620 | 0.188 | **0.186** |
| `datetime_fixed_offset_1024` | 95.297 | **91.237** | 108.419 | 107.371 |
| `datetime_fixed_offset_16` | 2.338 | 2.344 | 1.858 | **1.826** |
| `datetime_fixed_offset_scalar` | 0.700 | 0.700 | 0.287 | **0.287** |
| `datetime_naive_1024` | 59.326 | 56.053 | 30.080 | **29.470** |
| `datetime_naive_1024_naive_utc` | 61.814 | 58.370 | 32.299 | **31.328** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 53.294 | 50.508 | **25.451** | 25.555 |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 53.929 | 50.335 | **24.760** | 25.311 |
| `datetime_naive_1024_naive_utc_z` | 59.493 | 56.616 | **31.135** | 31.528 |
| `datetime_naive_1024_omit_microseconds` | 53.195 | 49.648 | 22.914 | **22.762** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 53.226 | 49.978 | **23.090** | 23.215 |
| `datetime_naive_1024_utc_z` | 59.487 | 56.571 | 30.597 | **29.834** |
| `datetime_naive_1024_zero_microseconds` | 53.098 | 49.614 | **23.600** | 23.801 |
| `datetime_naive_16` | 1.742 | 1.697 | 0.626 | **0.620** |
| `datetime_naive_scalar` | 0.639 | 0.645 | 0.200 | **0.196** |
| `datetime_named_zero_offset_1024` | 89.198 | **86.149** | 100.690 | 100.469 |
| `datetime_negative_offset_1024` | 95.092 | **92.086** | 108.851 | 108.971 |
| `datetime_passthrough` | 923.044 | 911.054 | 665.252 | **663.806** |
| `datetime_seconds_offset_1024` | 94.064 | **92.255** | 108.323 | 109.125 |
| `datetime_subclass` | 758.758 | 754.676 | **698.218** | 700.898 |
| `datetime_utc_1024` | 67.803 | **65.639** | 100.879 | 99.661 |
| `datetime_utc_1024_omit_microseconds` | 58.670 | **58.236** | 91.955 | 92.205 |
| `datetime_utc_1024_omit_microseconds_utc_z` | 58.828 | **58.304** | 91.166 | 91.268 |
| `datetime_utc_1024_utc_z` | 65.062 | **64.542** | 98.522 | 99.223 |
| `datetime_utc_1024_zero_microseconds` | 58.857 | **58.324** | 92.589 | 92.647 |
| `datetime_utc_16` | 1.924 | 1.834 | **1.726** | 1.729 |
| `datetime_utc_scalar` | 0.639 | 0.649 | 0.278 | **0.278** |
| `dict_control` | 0.342 | 0.266 | **0.228** | 0.230 |
| `list_control` | 11.119 | 10.893 | 4.468 | **4.450** |
| `string_control` | 0.178 | 0.172 | 0.170 | **0.168** |
| `time_1024_omit_microseconds` | 55.660 | 50.375 | **19.407** | 19.693 |
| `time_1024_zero_microseconds` | 55.342 | 49.921 | 19.950 | **19.859** |
| `time_scalar` | 0.625 | 0.639 | **0.194** | 0.197 |
| `uuid_list_control` | 905.233 | 79.972 | **44.324** | 45.955 |
| `uuid_scalar_control` | 1.656 | 0.662 | **0.225** | 0.231 |

## Different output bytes

These three cases are excluded from the orjson geometric mean.
The two jsonmodem columns match each other; the two orjson columns form a separate group.

Complete dumps latency (us). Bold compares only columns with equal output bytes. Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 222.302 | **167.482** | 170.935 | **147.131** |
| `time_1024` | 66.756 | **62.018** | 27.096 | **27.028** |
| `time_16` | 1.824 | **1.785** | 0.533 | **0.511** |
