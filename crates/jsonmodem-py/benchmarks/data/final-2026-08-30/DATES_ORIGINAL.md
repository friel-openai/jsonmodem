# Date/time: original control

Original is the existing PR #3 build (`b7fe329`).
Final is the changed implementation (`b0f3190`).
The reference is orjson 3.11.9. See [definitions and methods](README.md).

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

Complete dumps latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 214.644 | 228.914 | 85.524 | **84.978** |
| `dataclass_dates` | 3,077.007 | 255.374 | 190.908 | **188.782** |
| `date_1024` | 953.625 | 44.528 | 18.037 | **17.895** |
| `date_1024_options` | 927.247 | 45.495 | 18.332 | **18.302** |
| `date_16` | 15.712 | 1.394 | 0.421 | **0.416** |
| `date_scalar` | 1.708 | 0.617 | **0.162** | 0.188 |
| `datetime_fixed_offset_1024` | 2,797.418 | **93.797** | 109.094 | 108.345 |
| `datetime_fixed_offset_16` | 44.901 | 2.352 | 1.833 | **1.818** |
| `datetime_fixed_offset_scalar` | 3.551 | 0.707 | 0.288 | **0.282** |
| `datetime_naive_1024` | 1,873.235 | 56.986 | **30.047** | 31.355 |
| `datetime_naive_1024_naive_utc` | 2,720.251 | 59.455 | **32.117** | 32.341 |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 2,468.804 | 53.078 | 25.511 | **25.138** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 1,993.236 | 53.190 | 25.607 | **25.182** |
| `datetime_naive_1024_naive_utc_z` | 2,280.027 | 57.759 | 31.703 | **31.178** |
| `datetime_naive_1024_omit_microseconds` | 1,619.384 | 51.933 | 23.219 | **23.077** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 1,617.577 | 51.377 | 23.108 | **22.873** |
| `datetime_naive_1024_utc_z` | 1,877.256 | 57.468 | 30.459 | **29.630** |
| `datetime_naive_1024_zero_microseconds` | 1,586.845 | 53.076 | **23.385** | 23.660 |
| `datetime_naive_16` | 30.546 | 1.707 | **0.613** | 0.617 |
| `datetime_naive_scalar` | 2.658 | 0.635 | 0.197 | **0.196** |
| `datetime_named_zero_offset_1024` | 2,732.989 | **90.639** | 101.923 | 99.990 |
| `datetime_negative_offset_1024` | 2,763.724 | **95.658** | 109.512 | 109.436 |
| `datetime_passthrough` | 933.033 | 928.000 | 669.573 | **661.999** |
| `datetime_seconds_offset_1024` | 2,758.053 | **93.834** | 109.642 | 108.340 |
| `datetime_subclass` | 750.103 | 756.908 | 705.118 | **694.333** |
| `datetime_utc_1024` | 2,739.639 | **64.903** | 100.901 | 100.796 |
| `datetime_utc_1024_omit_microseconds` | 2,464.544 | **59.121** | 92.864 | 91.870 |
| `datetime_utc_1024_omit_microseconds_utc_z` | 2,017.594 | **59.049** | 92.859 | 91.562 |
| `datetime_utc_1024_utc_z` | 2,271.055 | **64.139** | 101.118 | 98.720 |
| `datetime_utc_1024_zero_microseconds` | 2,437.173 | **59.065** | 93.451 | 91.921 |
| `datetime_utc_16` | 44.786 | 1.850 | 1.761 | **1.716** |
| `datetime_utc_scalar` | 3.537 | 0.644 | **0.276** | 0.277 |
| `dict_control` | 0.304 | 0.317 | **0.227** | 0.232 |
| `list_control` | 11.044 | 11.134 | **4.407** | 4.450 |
| `string_control` | **0.173** | 0.178 | 0.175 | 0.174 |
| `time_1024_omit_microseconds` | 1,079.197 | 56.372 | **19.513** | 19.621 |
| `time_1024_zero_microseconds` | 1,054.112 | 56.038 | **19.645** | 19.842 |
| `time_scalar` | 2.143 | 0.627 | **0.176** | 0.177 |
| `uuid_list_control` | 883.575 | 917.261 | 45.482 | **44.840** |
| `uuid_scalar_control` | 1.651 | 1.662 | **0.228** | 0.230 |

## Different output bytes

These three cases are excluded from the orjson geometric mean.
The two jsonmodem columns match each other; the two orjson columns form a separate group.

Complete dumps latency (us). Bold compares only columns with equal output bytes. Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 5,030.053 | **178.106** | 151.950 | **150.913** |
| `time_1024` | 1,350.159 | **67.240** | 27.291 | **26.939** |
| `time_16` | 22.684 | **1.854** | 0.507 | **0.504** |
