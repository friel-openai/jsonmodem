# Date/time: rebuilt control

Rebuilt is a new compilation of unchanged PR #3 source (`b7fe329`).
Final is the changed implementation (`b0f3190`).
The reference is orjson 3.11.9. See [definitions and methods](README.md).

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

Complete dumps latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 215.796 | 225.104 | 85.795 | **84.166** |
| `dataclass_dates` | 3,130.774 | 253.151 | 190.828 | **189.400** |
| `date_1024` | 945.479 | 44.574 | 17.862 | **17.852** |
| `date_1024_options` | 935.874 | 45.106 | **18.197** | 18.284 |
| `date_16` | 15.604 | 1.400 | 0.448 | **0.417** |
| `date_scalar` | 1.715 | 0.624 | 0.192 | **0.189** |
| `datetime_fixed_offset_1024` | 2,750.179 | **93.839** | 109.848 | 109.154 |
| `datetime_fixed_offset_16` | 44.951 | 2.352 | 1.861 | **1.828** |
| `datetime_fixed_offset_scalar` | 3.594 | 0.711 | 0.291 | **0.281** |
| `datetime_naive_1024` | 1,898.100 | 58.066 | **29.918** | 30.083 |
| `datetime_naive_1024_naive_utc` | 2,725.492 | 60.943 | 32.918 | **32.564** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 2,448.847 | 53.673 | **25.229** | 25.318 |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 2,029.012 | 53.893 | **25.236** | 25.335 |
| `datetime_naive_1024_naive_utc_z` | 2,285.192 | 59.543 | 31.780 | **31.495** |
| `datetime_naive_1024_omit_microseconds` | 1,633.193 | 52.530 | **23.103** | 23.290 |
| `datetime_naive_1024_omit_microseconds_utc_z` | 1,629.919 | 52.592 | 23.053 | **22.896** |
| `datetime_naive_1024_utc_z` | 1,907.088 | 59.668 | **29.866** | 29.922 |
| `datetime_naive_1024_zero_microseconds` | 1,603.634 | 52.425 | **23.270** | 25.044 |
| `datetime_naive_16` | 31.073 | 1.731 | **0.612** | 0.621 |
| `datetime_naive_scalar` | 2.689 | 0.652 | 0.204 | **0.198** |
| `datetime_named_zero_offset_1024` | 2,760.069 | **90.442** | 101.461 | 101.341 |
| `datetime_negative_offset_1024` | 2,819.251 | **94.821** | 109.369 | 109.941 |
| `datetime_passthrough` | 933.347 | 926.181 | **667.016** | 667.257 |
| `datetime_seconds_offset_1024` | 2,771.422 | **93.890** | 110.159 | 108.740 |
| `datetime_subclass` | 743.060 | 760.746 | **698.158** | 701.629 |
| `datetime_utc_1024` | 2,729.748 | **65.922** | 102.165 | 100.799 |
| `datetime_utc_1024_omit_microseconds` | 2,490.102 | **59.024** | 92.083 | 92.012 |
| `datetime_utc_1024_omit_microseconds_utc_z` | 2,066.089 | **59.285** | 91.730 | 92.318 |
| `datetime_utc_1024_utc_z` | 2,290.810 | **63.360** | 99.627 | 99.302 |
| `datetime_utc_1024_zero_microseconds` | 2,423.866 | **58.850** | 92.106 | 93.118 |
| `datetime_utc_16` | 44.591 | 1.863 | **1.715** | 1.742 |
| `datetime_utc_scalar` | 3.577 | 0.651 | 0.281 | **0.277** |
| `dict_control` | 0.306 | 0.320 | 0.233 | **0.233** |
| `list_control` | 11.031 | 11.057 | **4.402** | 4.411 |
| `string_control` | 0.174 | 0.180 | **0.172** | 0.173 |
| `time_1024_omit_microseconds` | 1,091.912 | 56.095 | **19.397** | 19.988 |
| `time_1024_zero_microseconds` | 1,054.041 | 55.988 | 19.850 | **19.833** |
| `time_scalar` | 2.154 | 0.631 | 0.198 | **0.176** |
| `uuid_list_control` | 893.218 | 906.581 | 45.336 | **44.807** |
| `uuid_scalar_control` | 1.673 | 1.664 | 0.232 | **0.230** |

## Different output bytes

These three cases are excluded from the orjson geometric mean.
The two jsonmodem columns match each other; the two orjson columns form a separate group.

Complete dumps latency (us). Bold compares only columns with equal output bytes. Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 4,995.693 | **177.475** | 149.180 | **148.995** |
| `time_1024` | 1,362.405 | **67.072** | **26.880** | 26.926 |
| `time_16` | 22.609 | **1.846** | 0.529 | **0.506** |
