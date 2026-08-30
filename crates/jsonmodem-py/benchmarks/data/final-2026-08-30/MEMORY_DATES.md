# Date/time memory

Original is the existing PR #3 build; Rebuilt compiles that same source
again (`b7fe329`).
Final is the changed implementation (`b0f3190`).
The reference is orjson 3.11.9. See [definitions and methods](README.md).

[Summary](PERFORMANCE_FINAL.md). Medians of three process observations.
Memray uses one tracked call after ten warmups.
Peak live bytes are Memray's reported capture peak, not process RSS or a separate reconstruction.
RSS uses ten calls without warmup. Peak RSS is Linux VmHWM, including preparation; it is not ru_maxrss.
Four libraries and three repetitions do not fully balance execution positions. There is no memory mean.

Allocation requests (requests). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 24 | 24 | 24 | **17** |
| `dataclass_dates` | 62,491 | 62,491 | **24** | 1,041 |
| `date_1024` | 17,431 | 17,431 | 20 | **15** |
| `date_1024_options` | 17,433 | 17,433 | 22 | **17** |
| `date_16` | 289 | 289 | 14 | **11** |
| `date_scalar` | 33 | 33 | 13 | **11** |
| `datetime_fixed_offset_1024` | 66,585 | 66,585 | **22** | 1,041 |
| `datetime_fixed_offset_16` | 1,059 | 1,059 | **16** | 27 |
| `datetime_fixed_offset_scalar` | 81 | 81 | 13 | **12** |
| `datetime_naive_1024` | 42,008 | 42,008 | 21 | **16** |
| `datetime_naive_1024_naive_utc` | 57,371 | 57,371 | 24 | **19** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 50,202 | 50,202 | 23 | **18** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 40,986 | 40,986 | 23 | **18** |
| `datetime_naive_1024_naive_utc_z` | 48,154 | 48,154 | 23 | **18** |
| `datetime_naive_1024_omit_microseconds` | 34,842 | 34,842 | 23 | **18** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 34,842 | 34,842 | 23 | **18** |
| `datetime_naive_1024_utc_z` | 42,010 | 42,010 | 23 | **18** |
| `datetime_naive_1024_zero_microseconds` | 33,816 | 33,816 | 21 | **16** |
| `datetime_naive_16` | 674 | 674 | 15 | **11** |
| `datetime_naive_scalar` | 57 | 57 | 13 | **11** |
| `datetime_named_zero_offset_1024` | 62,489 | 62,489 | **22** | 1,041 |
| `datetime_negative_offset_1024` | 67,609 | 67,609 | **22** | 1,041 |
| `datetime_passthrough` | 9,242 | 9,242 | 9,242 | **5,139** |
| `datetime_seconds_offset_1024` | 66,585 | 66,585 | **22** | 1,041 |
| `datetime_subclass` | 5,145 | 5,145 | 5,145 | **5,139** |
| `datetime_utc_1024` | 62,489 | 62,489 | **22** | 1,041 |
| `datetime_utc_1024_omit_microseconds` | 55,322 | 55,322 | **23** | 1,042 |
| `datetime_utc_1024_omit_microseconds_utc_z` | 46,106 | 46,106 | **23** | 1,042 |
| `datetime_utc_1024_utc_z` | 53,274 | 53,274 | **23** | 1,042 |
| `datetime_utc_1024_zero_microseconds` | 54,296 | 54,296 | **21** | 1,040 |
| `datetime_utc_16` | 995 | 995 | **16** | 27 |
| `datetime_utc_scalar` | 77 | 77 | 13 | **12** |
| `dict_control` | 12 | 12 | 12 | **11** |
| `list_control` | 16 | 16 | 16 | **14** |
| `string_control` | 12 | 12 | 12 | **11** |
| `time_1024_omit_microseconds` | 19,481 | 19,481 | 22 | **17** |
| `time_1024_zero_microseconds` | 18,455 | 18,455 | 20 | **15** |
| `time_scalar` | 42 | 42 | 13 | **11** |
| `uuid_list_control` | 12,313 | 12,313 | 12,313 | **17** |
| `uuid_scalar_control` | 28 | 28 | 28 | **11** |

Allocation requests (requests). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 106,527 | 106,527 | **26** | 1,042 |
| `time_1024` | 26,648 | 26,648 | **21** | 16 |
| `time_16` | 434 | 434 | **15** | 11 |

Total allocated bytes (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 174.709 | 174.709 | 174.709 | **128.054** |
| `dataclass_dates` | 3,437.371 | 3,437.371 | **193.709** | 200.054 |
| `date_1024` | 1,229.511 | 1,229.511 | 53.660 | **31.989** |
| `date_1024_options` | 1,229.651 | 1,229.651 | 53.801 | **32.130** |
| `date_16` | 20.027 | 20.027 | **1.488** | 1.860 |
| `date_scalar` | 2.498 | 2.498 | **1.171** | 1.860 |
| `datetime_fixed_offset_1024` | 3,552.322 | 3,552.322 | **171.660** | 200.054 |
| `datetime_fixed_offset_16` | 56.316 | 56.316 | 3.332 | **2.985** |
| `datetime_fixed_offset_scalar` | 4.671 | 4.671 | **1.192** | 1.931 |
| `datetime_naive_1024` | 2,397.322 | 2,397.322 | 101.660 | **64.021** |
| `datetime_naive_1024_naive_utc` | 3,125.463 | 3,125.463 | 171.801 | **128.194** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 2,702.574 | 2,702.574 | 100.801 | **64.162** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 2,275.574 | 2,275.574 | 95.801 | **64.162** |
| `datetime_naive_1024_naive_utc_z` | 2,634.463 | 2,634.463 | 102.801 | **64.162** |
| `datetime_naive_1024_omit_microseconds` | 2,045.574 | 2,045.574 | 94.801 | **64.162** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 2,045.574 | 2,045.574 | 94.801 | **64.162** |
| `datetime_naive_1024_utc_z` | 2,397.463 | 2,397.463 | 101.801 | **64.162** |
| `datetime_naive_1024_zero_microseconds` | 2,013.434 | 2,013.434 | 94.660 | **64.021** |
| `datetime_naive_16` | 38.270 | 38.270 | 2.238 | **1.860** |
| `datetime_naive_scalar` | 3.605 | 3.605 | **1.187** | 1.860 |
| `datetime_named_zero_offset_1024` | 3,415.322 | 3,415.322 | **171.660** | 200.054 |
| `datetime_negative_offset_1024` | 3,584.322 | 3,584.322 | **171.660** | 200.054 |
| `datetime_passthrough` | 984.988 | 984.988 | 984.988 | **611.240** |
| `datetime_seconds_offset_1024` | 3,552.322 | 3,552.322 | **171.660** | 200.054 |
| `datetime_subclass` | 648.892 | 648.892 | 648.892 | **611.221** |
| `datetime_utc_1024` | 3,415.322 | 3,415.322 | **171.660** | 200.054 |
| `datetime_utc_1024_omit_microseconds` | 2,992.574 | 2,992.574 | **100.801** | 136.162 |
| `datetime_utc_1024_omit_microseconds_utc_z` | 2,565.574 | 2,565.574 | **95.801** | 136.162 |
| `datetime_utc_1024_utc_z` | 2,924.463 | 2,924.463 | **102.801** | 136.162 |
| `datetime_utc_1024_zero_microseconds` | 2,960.434 | 2,960.434 | **100.660** | 136.021 |
| `datetime_utc_16` | 54.176 | 54.176 | 3.332 | **2.985** |
| `datetime_utc_scalar` | 4.537 | 4.537 | **1.192** | 1.931 |
| `dict_control` | **1.149** | **1.149** | **1.149** | 1.860 |
| `list_control` | **12.527** | **12.527** | **12.527** | 15.957 |
| `string_control` | **1.125** | **1.125** | **1.125** | 1.860 |
| `time_1024_omit_microseconds` | 1,285.903 | 1,285.903 | 51.801 | **32.130** |
| `time_1024_zero_microseconds` | 1,253.763 | 1,253.763 | 51.660 | **31.989** |
| `time_scalar` | 2.885 | 2.885 | **1.176** | 1.860 |
| `uuid_list_control` | 1,286.312 | 1,286.312 | 1,286.312 | **128.054** |
| `uuid_scalar_control` | 2.461 | 2.461 | 2.461 | **1.860** |

Total allocated bytes (KiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 6,334.007 | 6,334.007 | **346.784** | 328.086 |
| `time_1024` | 1,658.651 | 1,658.651 | **90.660** | 64.021 |
| `time_16` | 26.738 | 26.738 | **2.066** | 1.860 |

Peak live bytes tracked by Memray (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 102.660 | 102.660 | 102.660 | **64.610** |
| `dataclass_dates` | 121.889 | 121.889 | 121.660 | **64.681** |
| `date_1024` | 29.791 | 29.791 | 29.611 | **16.610** |
| `date_1024_options` | 29.932 | 29.932 | 29.752 | **16.751** |
| `date_16` | 1.849 | 1.849 | **1.064** | 1.610 |
| `date_scalar` | 1.724 | 1.724 | **0.877** | 1.610 |
| `datetime_fixed_offset_1024` | 99.840 | 99.938 | 99.611 | **64.681** |
| `datetime_fixed_offset_16` | 2.732 | 2.732 | 2.158 | **1.681** |
| `datetime_fixed_offset_scalar` | 1.857 | 1.857 | **0.894** | 1.681 |
| `datetime_naive_1024` | 61.791 | 61.791 | 61.611 | **32.610** |
| `datetime_naive_1024_naive_utc` | 99.932 | 99.932 | 99.752 | **64.751** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 60.932 | 60.932 | 60.752 | **32.751** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 55.932 | 55.932 | 55.752 | **32.751** |
| `datetime_naive_1024_naive_utc_z` | 62.932 | 62.932 | 62.752 | **32.751** |
| `datetime_naive_1024_omit_microseconds` | 54.932 | 54.932 | 54.752 | **32.751** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 54.932 | 54.932 | 54.752 | **32.751** |
| `datetime_naive_1024_utc_z` | 61.932 | 61.932 | 61.752 | **32.751** |
| `datetime_naive_1024_zero_microseconds` | 54.791 | 54.791 | 54.611 | **32.610** |
| `datetime_naive_16` | 2.148 | 2.148 | **1.564** | 1.610 |
| `datetime_naive_scalar` | 1.772 | 1.772 | **0.888** | 1.610 |
| `datetime_named_zero_offset_1024` | 99.840 | 99.889 | 99.611 | **64.681** |
| `datetime_negative_offset_1024` | 99.840 | 99.889 | 99.611 | **64.681** |
| `datetime_passthrough` | 61.939 | 61.939 | 61.939 | **33.157** |
| `datetime_seconds_offset_1024` | 99.840 | 99.938 | 99.611 | **64.681** |
| `datetime_subclass` | 61.854 | 61.854 | 61.854 | **33.149** |
| `datetime_utc_1024` | 99.840 | 99.840 | 99.611 | **64.681** |
| `datetime_utc_1024_omit_microseconds` | 61.664 | 62.201 | 60.752 | **32.821** |
| `datetime_utc_1024_omit_microseconds_utc_z` | 56.518 | 56.713 | 55.752 | **32.821** |
| `datetime_utc_1024_utc_z` | 62.980 | 62.980 | 62.752 | **32.821** |
| `datetime_utc_1024_zero_microseconds` | 60.986 | 62.256 | 60.611 | **32.681** |
| `datetime_utc_16` | 2.697 | 2.746 | 2.158 | **1.681** |
| `datetime_utc_scalar` | 1.794 | 1.794 | **0.894** | 1.681 |
| `dict_control` | **0.899** | **0.899** | **0.899** | 1.610 |
| `list_control` | **8.527** | **8.527** | **8.527** | 8.610 |
| `string_control` | **0.875** | **0.875** | **0.875** | 1.610 |
| `time_1024_omit_microseconds` | 27.932 | 27.932 | 27.752 | **16.751** |
| `time_1024_zero_microseconds` | 27.791 | 27.791 | 27.611 | **16.610** |
| `time_scalar` | 1.726 | 1.726 | **0.877** | 1.610 |
| `uuid_list_control` | 103.791 | 103.791 | 103.791 | **64.610** |
| `uuid_scalar_control` | 1.854 | 1.854 | 1.854 | **1.610** |

Peak live bytes tracked by Memray (KiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 195.091 | 195.042 | **194.735** | 128.681 |
| `time_1024` | 50.791 | 50.791 | **50.611** | 32.610 |
| `time_16` | 2.101 | 2.101 | **1.393** | 1.610 |

Peak RSS, including preparation (Linux VmHWM) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 24.367 | 24.211 | 24.230 | **23.719** |
| `dataclass_dates` | 24.285 | 24.297 | 24.270 | **23.695** |
| `date_1024` | 24.398 | 24.309 | 24.387 | **23.734** |
| `date_1024_options` | 24.309 | 24.246 | 24.340 | **23.645** |
| `date_16` | 24.309 | 24.406 | 24.301 | **23.715** |
| `date_scalar` | 24.238 | 24.285 | 24.352 | **23.688** |
| `datetime_fixed_offset_1024` | 24.254 | 24.414 | 24.434 | **23.762** |
| `datetime_fixed_offset_16` | 24.246 | 24.246 | 24.371 | **23.699** |
| `datetime_fixed_offset_scalar` | 24.254 | 24.297 | 24.395 | **23.699** |
| `datetime_naive_1024` | 24.246 | 24.332 | 24.422 | **23.688** |
| `datetime_naive_1024_naive_utc` | 24.398 | 24.215 | 24.273 | **23.680** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 24.332 | 24.238 | 24.430 | **23.773** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 24.289 | 24.410 | 24.328 | **23.684** |
| `datetime_naive_1024_naive_utc_z` | 24.457 | 24.309 | 24.344 | **23.781** |
| `datetime_naive_1024_omit_microseconds` | 24.348 | 24.203 | 24.477 | **23.766** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 24.418 | 24.332 | 24.430 | **23.711** |
| `datetime_naive_1024_utc_z` | 24.254 | 24.238 | 24.387 | **23.711** |
| `datetime_naive_1024_zero_microseconds` | 24.137 | 24.359 | 24.336 | **23.770** |
| `datetime_naive_16` | 24.309 | 24.332 | 24.242 | **23.773** |
| `datetime_naive_scalar` | 24.473 | 24.250 | 24.219 | **23.719** |
| `datetime_named_zero_offset_1024` | 24.410 | 24.348 | 24.375 | **23.621** |
| `datetime_negative_offset_1024` | 24.254 | 24.379 | 24.273 | **23.734** |
| `datetime_passthrough` | 24.277 | 24.309 | 24.168 | **23.695** |
| `datetime_seconds_offset_1024` | 24.410 | 24.246 | 24.441 | **23.613** |
| `datetime_subclass` | 24.348 | 24.301 | 24.449 | **23.699** |
| `datetime_utc_1024` | 24.312 | 24.352 | 24.426 | **23.730** |
| `datetime_utc_1024_omit_microseconds` | 24.297 | 24.410 | 24.344 | **23.777** |
| `datetime_utc_1024_omit_microseconds_utc_z` | 24.328 | 24.301 | 24.492 | **23.758** |
| `datetime_utc_1024_utc_z` | 24.340 | 24.410 | 24.430 | **23.812** |
| `datetime_utc_1024_zero_microseconds` | 24.332 | 24.402 | 24.445 | **23.621** |
| `datetime_utc_16` | 24.387 | 24.262 | 24.344 | **23.723** |
| `datetime_utc_scalar` | 24.312 | 24.312 | 24.441 | **23.762** |
| `dict_control` | 24.414 | 24.309 | 24.340 | **23.730** |
| `list_control` | 24.215 | 24.246 | 24.453 | **23.695** |
| `string_control` | 24.289 | 24.418 | 24.227 | **23.734** |
| `time_1024_omit_microseconds` | 24.344 | 24.328 | 24.270 | **23.715** |
| `time_1024_zero_microseconds` | 24.250 | 24.410 | 24.379 | **23.773** |
| `time_scalar` | 24.406 | 24.410 | 24.328 | **23.762** |
| `uuid_list_control` | 24.410 | 24.359 | 24.223 | **23.625** |
| `uuid_scalar_control` | 24.402 | 24.266 | 24.449 | **23.688** |

Peak RSS, including preparation (Linux VmHWM) (MiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | **24.203** | 24.246 | 24.234 | 23.703 |
| `time_1024` | 24.391 | **24.328** | 24.340 | 23.699 |
| `time_16` | **24.332** | 24.352 | 24.445 | 23.621 |

Prepared RSS (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 24.367 | 24.211 | 24.230 | **23.719** |
| `dataclass_dates` | 24.285 | 24.297 | 24.270 | **23.695** |
| `date_1024` | 24.398 | 24.309 | 24.387 | **23.734** |
| `date_1024_options` | 24.309 | 24.246 | 24.340 | **23.645** |
| `date_16` | 24.309 | 24.406 | 24.301 | **23.715** |
| `date_scalar` | 24.238 | 24.285 | 24.352 | **23.688** |
| `datetime_fixed_offset_1024` | 24.254 | 24.414 | 24.434 | **23.762** |
| `datetime_fixed_offset_16` | 24.246 | 24.246 | 24.371 | **23.699** |
| `datetime_fixed_offset_scalar` | 24.254 | 24.297 | 24.395 | **23.699** |
| `datetime_naive_1024` | 24.246 | 24.332 | 24.422 | **23.688** |
| `datetime_naive_1024_naive_utc` | 24.398 | 24.215 | 24.273 | **23.680** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 24.332 | 24.238 | 24.430 | **23.773** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 24.289 | 24.410 | 24.328 | **23.684** |
| `datetime_naive_1024_naive_utc_z` | 24.457 | 24.309 | 24.344 | **23.781** |
| `datetime_naive_1024_omit_microseconds` | 24.348 | 24.203 | 24.477 | **23.766** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 24.418 | 24.332 | 24.430 | **23.711** |
| `datetime_naive_1024_utc_z` | 24.254 | 24.238 | 24.387 | **23.711** |
| `datetime_naive_1024_zero_microseconds` | 24.137 | 24.359 | 24.336 | **23.770** |
| `datetime_naive_16` | 24.309 | 24.332 | 24.242 | **23.773** |
| `datetime_naive_scalar` | 24.473 | 24.250 | 24.219 | **23.719** |
| `datetime_named_zero_offset_1024` | 24.410 | 24.348 | 24.375 | **23.621** |
| `datetime_negative_offset_1024` | 24.254 | 24.379 | 24.273 | **23.734** |
| `datetime_passthrough` | 24.277 | 24.309 | 24.168 | **23.695** |
| `datetime_seconds_offset_1024` | 24.410 | 24.246 | 24.441 | **23.613** |
| `datetime_subclass` | 24.348 | 24.301 | 24.449 | **23.699** |
| `datetime_utc_1024` | 24.312 | 24.352 | 24.426 | **23.730** |
| `datetime_utc_1024_omit_microseconds` | 24.297 | 24.410 | 24.344 | **23.777** |
| `datetime_utc_1024_omit_microseconds_utc_z` | 24.328 | 24.301 | 24.492 | **23.758** |
| `datetime_utc_1024_utc_z` | 24.340 | 24.410 | 24.430 | **23.812** |
| `datetime_utc_1024_zero_microseconds` | 24.332 | 24.402 | 24.445 | **23.621** |
| `datetime_utc_16` | 24.387 | 24.262 | 24.344 | **23.723** |
| `datetime_utc_scalar` | 24.312 | 24.312 | 24.441 | **23.762** |
| `dict_control` | 24.414 | 24.309 | 24.340 | **23.730** |
| `list_control` | 24.215 | 24.246 | 24.453 | **23.695** |
| `string_control` | 24.289 | 24.418 | 24.227 | **23.734** |
| `time_1024_omit_microseconds` | 24.344 | 24.328 | 24.270 | **23.715** |
| `time_1024_zero_microseconds` | 24.250 | 24.410 | 24.379 | **23.773** |
| `time_scalar` | 24.406 | 24.410 | 24.328 | **23.762** |
| `uuid_list_control` | 24.410 | 24.359 | 24.223 | **23.625** |
| `uuid_scalar_control` | 24.402 | 24.266 | 24.449 | **23.688** |

Prepared RSS (Linux VmRSS) (MiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | **24.203** | 24.246 | 24.234 | 23.703 |
| `time_1024` | 24.391 | **24.328** | 24.340 | 23.699 |
| `time_16` | **24.332** | 24.352 | 24.445 | 23.621 |

RSS with the first result alive (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 24.367 | 24.211 | 24.230 | **23.719** |
| `dataclass_dates` | 24.285 | 24.297 | 24.270 | **23.695** |
| `date_1024` | 24.398 | 24.309 | 24.387 | **23.734** |
| `date_1024_options` | 24.309 | 24.246 | 24.340 | **23.645** |
| `date_16` | 24.309 | 24.406 | 24.301 | **23.715** |
| `date_scalar` | 24.238 | 24.285 | 24.352 | **23.688** |
| `datetime_fixed_offset_1024` | 24.254 | 24.414 | 24.434 | **23.762** |
| `datetime_fixed_offset_16` | 24.246 | 24.246 | 24.371 | **23.699** |
| `datetime_fixed_offset_scalar` | 24.254 | 24.297 | 24.395 | **23.699** |
| `datetime_naive_1024` | 24.246 | 24.332 | 24.422 | **23.688** |
| `datetime_naive_1024_naive_utc` | 24.398 | 24.215 | 24.273 | **23.680** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 24.332 | 24.238 | 24.430 | **23.773** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 24.289 | 24.410 | 24.328 | **23.684** |
| `datetime_naive_1024_naive_utc_z` | 24.457 | 24.309 | 24.344 | **23.781** |
| `datetime_naive_1024_omit_microseconds` | 24.348 | 24.203 | 24.477 | **23.766** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 24.418 | 24.332 | 24.430 | **23.711** |
| `datetime_naive_1024_utc_z` | 24.254 | 24.238 | 24.387 | **23.711** |
| `datetime_naive_1024_zero_microseconds` | 24.137 | 24.359 | 24.336 | **23.770** |
| `datetime_naive_16` | 24.309 | 24.332 | 24.242 | **23.773** |
| `datetime_naive_scalar` | 24.473 | 24.250 | 24.219 | **23.719** |
| `datetime_named_zero_offset_1024` | 24.410 | 24.348 | 24.375 | **23.621** |
| `datetime_negative_offset_1024` | 24.254 | 24.379 | 24.273 | **23.734** |
| `datetime_passthrough` | 24.277 | 24.309 | 24.168 | **23.695** |
| `datetime_seconds_offset_1024` | 24.410 | 24.246 | 24.441 | **23.613** |
| `datetime_subclass` | 24.348 | 24.301 | 24.449 | **23.699** |
| `datetime_utc_1024` | 24.312 | 24.352 | 24.426 | **23.730** |
| `datetime_utc_1024_omit_microseconds` | 24.297 | 24.410 | 24.344 | **23.777** |
| `datetime_utc_1024_omit_microseconds_utc_z` | 24.328 | 24.301 | 24.492 | **23.758** |
| `datetime_utc_1024_utc_z` | 24.340 | 24.410 | 24.430 | **23.812** |
| `datetime_utc_1024_zero_microseconds` | 24.332 | 24.402 | 24.445 | **23.621** |
| `datetime_utc_16` | 24.387 | 24.262 | 24.344 | **23.723** |
| `datetime_utc_scalar` | 24.312 | 24.312 | 24.441 | **23.762** |
| `dict_control` | 24.414 | 24.309 | 24.340 | **23.730** |
| `list_control` | 24.215 | 24.246 | 24.453 | **23.695** |
| `string_control` | 24.289 | 24.418 | 24.227 | **23.734** |
| `time_1024_omit_microseconds` | 24.344 | 24.328 | 24.270 | **23.715** |
| `time_1024_zero_microseconds` | 24.250 | 24.410 | 24.379 | **23.773** |
| `time_scalar` | 24.406 | 24.410 | 24.328 | **23.762** |
| `uuid_list_control` | 24.410 | 24.359 | 24.223 | **23.625** |
| `uuid_scalar_control` | 24.402 | 24.266 | 24.449 | **23.688** |

RSS with the first result alive (Linux VmRSS) (MiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | **24.203** | 24.246 | 24.234 | 23.703 |
| `time_1024` | 24.391 | **24.328** | 24.340 | 23.699 |
| `time_16` | **24.332** | 24.352 | 24.445 | 23.621 |
