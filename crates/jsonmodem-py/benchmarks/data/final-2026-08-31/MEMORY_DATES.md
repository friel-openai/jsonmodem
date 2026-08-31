# Date/time memory

[Summary](PERFORMANCE_FINAL.md). Medians of three process observations.
Memray uses one tracked call after ten warmups.
Peak live bytes are Memray's reported capture peak, not process RSS or a separate reconstruction.
RSS uses ten calls without warmup. Peak RSS is Linux VmHWM, including preparation; it is not ru_maxrss.
Four libraries and three repetitions do not fully balance execution positions. There is no memory mean.

Allocation requests (requests). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 24 | 24 | 24 | **17** |
| `dataclass_dates` | **24** | **24** | **24** | 1,041 |
| `date_1024` | 20 | 20 | 20 | **15** |
| `date_1024_options` | 22 | 22 | 22 | **17** |
| `date_16` | 14 | 14 | 14 | **11** |
| `date_scalar` | 13 | 13 | 13 | **11** |
| `datetime_fixed_offset_1024` | **22** | **22** | **22** | 1,041 |
| `datetime_fixed_offset_16` | **16** | **16** | **16** | 27 |
| `datetime_fixed_offset_scalar` | 13 | 13 | 13 | **12** |
| `datetime_naive_1024` | 21 | 21 | 21 | **16** |
| `datetime_naive_1024_naive_utc` | 24 | 24 | 24 | **19** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 23 | 23 | 23 | **18** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 23 | 23 | 23 | **18** |
| `datetime_naive_1024_naive_utc_z` | 23 | 23 | 23 | **18** |
| `datetime_naive_1024_omit_microseconds` | 23 | 23 | 23 | **18** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 23 | 23 | 23 | **18** |
| `datetime_naive_1024_utc_z` | 23 | 23 | 23 | **18** |
| `datetime_naive_1024_zero_microseconds` | 21 | 21 | 21 | **16** |
| `datetime_naive_16` | 15 | 15 | 15 | **11** |
| `datetime_naive_scalar` | 13 | 13 | 13 | **11** |
| `datetime_named_zero_offset_1024` | **22** | **22** | **22** | 1,041 |
| `datetime_negative_offset_1024` | **22** | **22** | **22** | 1,041 |
| `datetime_passthrough` | 9,242 | 9,242 | 9,242 | **5,139** |
| `datetime_seconds_offset_1024` | **22** | **22** | **22** | 1,041 |
| `datetime_subclass` | 5,145 | 5,145 | 5,145 | **5,139** |
| `datetime_utc_1024` | **22** | **22** | **22** | 1,041 |
| `datetime_utc_1024_omit_microseconds` | **23** | **23** | **23** | 1,042 |
| `datetime_utc_1024_omit_microseconds_utc_z` | **23** | **23** | **23** | 1,042 |
| `datetime_utc_1024_utc_z` | **23** | **23** | **23** | 1,042 |
| `datetime_utc_1024_zero_microseconds` | **21** | **21** | **21** | 1,040 |
| `datetime_utc_16` | **16** | **16** | **16** | 27 |
| `datetime_utc_scalar` | 13 | 13 | 13 | **12** |
| `dict_control` | 12 | 12 | 12 | **11** |
| `list_control` | 16 | 16 | 16 | **14** |
| `string_control` | 12 | 12 | 12 | **11** |
| `time_1024_omit_microseconds` | 22 | 22 | 22 | **17** |
| `time_1024_zero_microseconds` | 20 | 20 | 20 | **15** |
| `time_scalar` | 13 | 13 | 13 | **11** |
| `uuid_list_control` | 12,313 | 12,313 | 22 | **17** |
| `uuid_scalar_control` | 28 | 28 | 13 | **11** |

Allocation requests (requests). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | **26** | **26** | **26** | 1,042 |
| `time_1024` | **21** | **21** | **21** | 16 |
| `time_16` | **15** | **15** | **15** | 11 |

Total allocated bytes (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 174.709 | 174.709 | 174.709 | **128.054** |
| `dataclass_dates` | **193.709** | **193.709** | **193.709** | 200.054 |
| `date_1024` | 53.660 | 53.660 | 53.660 | **31.989** |
| `date_1024_options` | 53.801 | 53.801 | 53.801 | **32.130** |
| `date_16` | **1.488** | **1.488** | **1.488** | 1.860 |
| `date_scalar` | **1.171** | **1.171** | **1.171** | 1.860 |
| `datetime_fixed_offset_1024` | **171.660** | **171.660** | **171.660** | 200.054 |
| `datetime_fixed_offset_16` | 3.332 | 3.332 | 3.332 | **2.985** |
| `datetime_fixed_offset_scalar` | **1.192** | **1.192** | **1.192** | 1.931 |
| `datetime_naive_1024` | 101.660 | 101.660 | 101.660 | **64.021** |
| `datetime_naive_1024_naive_utc` | 171.801 | 171.801 | 171.801 | **128.194** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 100.801 | 100.801 | 100.801 | **64.162** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 95.801 | 95.801 | 95.801 | **64.162** |
| `datetime_naive_1024_naive_utc_z` | 102.801 | 102.801 | 102.801 | **64.162** |
| `datetime_naive_1024_omit_microseconds` | 94.801 | 94.801 | 94.801 | **64.162** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 94.801 | 94.801 | 94.801 | **64.162** |
| `datetime_naive_1024_utc_z` | 101.801 | 101.801 | 101.801 | **64.162** |
| `datetime_naive_1024_zero_microseconds` | 94.660 | 94.660 | 94.660 | **64.021** |
| `datetime_naive_16` | 2.238 | 2.238 | 2.238 | **1.860** |
| `datetime_naive_scalar` | **1.187** | **1.187** | **1.187** | 1.860 |
| `datetime_named_zero_offset_1024` | **171.660** | **171.660** | **171.660** | 200.054 |
| `datetime_negative_offset_1024` | **171.660** | **171.660** | **171.660** | 200.054 |
| `datetime_passthrough` | 984.988 | 984.988 | 984.988 | **611.240** |
| `datetime_seconds_offset_1024` | **171.660** | **171.660** | **171.660** | 200.054 |
| `datetime_subclass` | 648.892 | 648.892 | 648.892 | **611.221** |
| `datetime_utc_1024` | **171.660** | **171.660** | **171.660** | 200.054 |
| `datetime_utc_1024_omit_microseconds` | **100.801** | **100.801** | **100.801** | 136.162 |
| `datetime_utc_1024_omit_microseconds_utc_z` | **95.801** | **95.801** | **95.801** | 136.162 |
| `datetime_utc_1024_utc_z` | **102.801** | **102.801** | **102.801** | 136.162 |
| `datetime_utc_1024_zero_microseconds` | **100.660** | **100.660** | **100.660** | 136.021 |
| `datetime_utc_16` | 3.332 | 3.332 | 3.332 | **2.985** |
| `datetime_utc_scalar` | **1.192** | **1.192** | **1.192** | 1.931 |
| `dict_control` | **1.149** | **1.149** | **1.149** | 1.860 |
| `list_control` | **12.527** | **12.527** | **12.527** | 15.957 |
| `string_control` | **1.125** | **1.125** | **1.125** | 1.860 |
| `time_1024_omit_microseconds` | 51.801 | 51.801 | 51.801 | **32.130** |
| `time_1024_zero_microseconds` | 51.660 | 51.660 | 51.660 | **31.989** |
| `time_scalar` | **1.176** | **1.176** | **1.176** | 1.860 |
| `uuid_list_control` | 1,286.312 | 1,286.312 | 175.660 | **128.054** |
| `uuid_scalar_control` | 2.461 | 2.461 | **1.196** | 1.860 |

Total allocated bytes (KiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | **346.784** | **346.784** | **346.784** | 328.086 |
| `time_1024` | **90.660** | **90.660** | **90.660** | 64.021 |
| `time_16` | **2.066** | **2.066** | **2.066** | 1.860 |

Peak live bytes tracked by Memray (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 102.660 | 102.660 | 102.660 | **64.610** |
| `dataclass_dates` | 121.660 | 121.660 | 121.660 | **64.681** |
| `date_1024` | 29.611 | 29.611 | 29.611 | **16.610** |
| `date_1024_options` | 29.752 | 29.752 | 29.752 | **16.751** |
| `date_16` | **1.064** | **1.064** | **1.064** | 1.610 |
| `date_scalar` | **0.877** | **0.877** | **0.877** | 1.610 |
| `datetime_fixed_offset_1024` | 99.611 | 99.611 | 99.611 | **64.681** |
| `datetime_fixed_offset_16` | 2.158 | 2.158 | 2.158 | **1.681** |
| `datetime_fixed_offset_scalar` | **0.894** | **0.894** | **0.894** | 1.681 |
| `datetime_naive_1024` | 61.611 | 61.611 | 61.611 | **32.610** |
| `datetime_naive_1024_naive_utc` | 99.752 | 99.752 | 99.752 | **64.751** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 60.752 | 60.752 | 60.752 | **32.751** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 55.752 | 55.752 | 55.752 | **32.751** |
| `datetime_naive_1024_naive_utc_z` | 62.752 | 62.752 | 62.752 | **32.751** |
| `datetime_naive_1024_omit_microseconds` | 54.752 | 54.752 | 54.752 | **32.751** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 54.752 | 54.752 | 54.752 | **32.751** |
| `datetime_naive_1024_utc_z` | 61.752 | 61.752 | 61.752 | **32.751** |
| `datetime_naive_1024_zero_microseconds` | 54.611 | 54.611 | 54.611 | **32.610** |
| `datetime_naive_16` | **1.564** | **1.564** | **1.564** | 1.610 |
| `datetime_naive_scalar` | **0.888** | **0.888** | **0.888** | 1.610 |
| `datetime_named_zero_offset_1024` | 99.611 | 99.611 | 99.611 | **64.681** |
| `datetime_negative_offset_1024` | 99.611 | 99.611 | 99.611 | **64.681** |
| `datetime_passthrough` | 61.939 | 61.939 | 61.939 | **33.157** |
| `datetime_seconds_offset_1024` | 99.611 | 99.611 | 99.611 | **64.681** |
| `datetime_subclass` | 61.854 | 61.854 | 61.854 | **33.149** |
| `datetime_utc_1024` | 99.611 | 99.611 | 99.611 | **64.681** |
| `datetime_utc_1024_omit_microseconds` | 60.752 | 60.752 | 60.752 | **32.821** |
| `datetime_utc_1024_omit_microseconds_utc_z` | 55.752 | 55.752 | 55.752 | **32.821** |
| `datetime_utc_1024_utc_z` | 62.752 | 62.752 | 62.752 | **32.821** |
| `datetime_utc_1024_zero_microseconds` | 60.611 | 60.611 | 60.611 | **32.681** |
| `datetime_utc_16` | 2.158 | 2.158 | 2.158 | **1.681** |
| `datetime_utc_scalar` | **0.894** | **0.894** | **0.894** | 1.681 |
| `dict_control` | **0.899** | **0.899** | **0.899** | 1.610 |
| `list_control` | **8.527** | **8.527** | **8.527** | 8.610 |
| `string_control` | **0.875** | **0.875** | **0.875** | 1.610 |
| `time_1024_omit_microseconds` | 27.752 | 27.752 | 27.752 | **16.751** |
| `time_1024_zero_microseconds` | 27.611 | 27.611 | 27.611 | **16.610** |
| `time_scalar` | **0.877** | **0.877** | **0.877** | 1.610 |
| `uuid_list_control` | 103.791 | 103.791 | 103.611 | **64.610** |
| `uuid_scalar_control` | 1.854 | 1.854 | **0.897** | 1.610 |

Peak live bytes tracked by Memray (KiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | **194.735** | **194.735** | **194.735** | 128.681 |
| `time_1024` | **50.611** | **50.611** | **50.611** | 32.610 |
| `time_16` | **1.393** | **1.393** | **1.393** | 1.610 |

Peak RSS, including preparation (Linux VmHWM) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 27.973 | 27.891 | 28.031 | **27.367** |
| `dataclass_dates` | 27.926 | 27.984 | 28.016 | **27.367** |
| `date_1024` | 27.953 | 27.953 | 27.871 | **27.340** |
| `date_1024_options` | 27.969 | 27.984 | 28.016 | **27.465** |
| `date_16` | 27.984 | 27.996 | 27.918 | **27.336** |
| `date_scalar` | 27.965 | 28.008 | 27.918 | **27.355** |
| `datetime_fixed_offset_1024` | 27.953 | 27.984 | 27.910 | **27.352** |
| `datetime_fixed_offset_16` | 27.965 | 27.969 | 27.875 | **27.402** |
| `datetime_fixed_offset_scalar` | 27.887 | 27.910 | 27.949 | **27.348** |
| `datetime_naive_1024` | 27.965 | 28.047 | 27.949 | **27.305** |
| `datetime_naive_1024_naive_utc` | 28.008 | 27.969 | 27.871 | **27.449** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 27.930 | 28.000 | 28.023 | **27.316** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 28.047 | 27.965 | 27.902 | **27.293** |
| `datetime_naive_1024_naive_utc_z` | 28.047 | 28.020 | 27.914 | **27.352** |
| `datetime_naive_1024_omit_microseconds` | 27.984 | 27.977 | 28.027 | **27.332** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 28.043 | 28.055 | 28.016 | **27.402** |
| `datetime_naive_1024_utc_z` | 28.039 | 27.996 | 28.090 | **27.289** |
| `datetime_naive_1024_zero_microseconds` | 27.891 | 27.984 | 28.027 | **27.465** |
| `datetime_naive_16` | 27.984 | 28.020 | 27.965 | **27.305** |
| `datetime_naive_scalar` | 28.008 | 27.895 | 28.008 | **27.340** |
| `datetime_named_zero_offset_1024` | 28.000 | 27.961 | 28.000 | **27.320** |
| `datetime_negative_offset_1024` | 28.016 | 27.984 | 28.012 | **27.246** |
| `datetime_passthrough` | 28.004 | 27.969 | 28.090 | **27.398** |
| `datetime_seconds_offset_1024` | 28.004 | 27.898 | 27.949 | **27.352** |
| `datetime_subclass` | 27.941 | 27.996 | 27.906 | **27.336** |
| `datetime_utc_1024` | 27.965 | 27.879 | 28.023 | **27.426** |
| `datetime_utc_1024_omit_microseconds` | 27.910 | 28.023 | 27.949 | **27.367** |
| `datetime_utc_1024_omit_microseconds_utc_z` | 27.969 | 28.000 | 27.938 | **27.406** |
| `datetime_utc_1024_utc_z` | 27.953 | 27.992 | 27.891 | **27.395** |
| `datetime_utc_1024_zero_microseconds` | 28.000 | 27.934 | 27.934 | **27.355** |
| `datetime_utc_16` | 28.016 | 27.961 | 27.863 | **27.340** |
| `datetime_utc_scalar` | 27.957 | 27.895 | 28.000 | **27.410** |
| `dict_control` | 27.953 | 27.914 | 28.000 | **27.320** |
| `list_control` | 27.914 | 27.969 | 27.965 | **27.398** |
| `string_control` | 28.012 | 27.996 | 27.973 | **27.305** |
| `time_1024_omit_microseconds` | 27.895 | 27.895 | 27.934 | **27.371** |
| `time_1024_zero_microseconds` | 27.984 | 27.984 | 27.949 | **27.250** |
| `time_scalar` | 28.031 | 28.039 | 27.902 | **27.402** |
| `uuid_list_control` | 28.020 | 27.906 | 28.105 | **27.316** |
| `uuid_scalar_control` | 27.969 | 28.059 | 27.980 | **27.418** |

Peak RSS, including preparation (Linux VmHWM) (MiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 28.012 | **27.969** | 27.988 | 27.406 |
| `time_1024` | **27.895** | 28.031 | 27.902 | 27.398 |
| `time_16` | 27.965 | 27.965 | **27.930** | 27.328 |

Prepared RSS (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 27.973 | 27.891 | 28.031 | **27.367** |
| `dataclass_dates` | 27.926 | 27.984 | 28.016 | **27.367** |
| `date_1024` | 27.953 | 27.953 | 27.871 | **27.340** |
| `date_1024_options` | 27.969 | 27.984 | 28.016 | **27.465** |
| `date_16` | 27.984 | 27.996 | 27.918 | **27.336** |
| `date_scalar` | 27.965 | 28.008 | 27.918 | **27.355** |
| `datetime_fixed_offset_1024` | 27.953 | 27.984 | 27.910 | **27.352** |
| `datetime_fixed_offset_16` | 27.965 | 27.969 | 27.875 | **27.402** |
| `datetime_fixed_offset_scalar` | 27.887 | 27.910 | 27.949 | **27.348** |
| `datetime_naive_1024` | 27.965 | 28.047 | 27.949 | **27.305** |
| `datetime_naive_1024_naive_utc` | 28.008 | 27.969 | 27.871 | **27.449** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 27.930 | 28.000 | 28.023 | **27.316** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 28.047 | 27.965 | 27.902 | **27.293** |
| `datetime_naive_1024_naive_utc_z` | 28.047 | 28.020 | 27.914 | **27.352** |
| `datetime_naive_1024_omit_microseconds` | 27.984 | 27.977 | 28.027 | **27.332** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 28.043 | 28.055 | 28.016 | **27.402** |
| `datetime_naive_1024_utc_z` | 28.039 | 27.996 | 28.090 | **27.289** |
| `datetime_naive_1024_zero_microseconds` | 27.891 | 27.984 | 28.027 | **27.465** |
| `datetime_naive_16` | 27.984 | 28.020 | 27.965 | **27.305** |
| `datetime_naive_scalar` | 28.008 | 27.895 | 28.008 | **27.340** |
| `datetime_named_zero_offset_1024` | 28.000 | 27.961 | 28.000 | **27.320** |
| `datetime_negative_offset_1024` | 28.016 | 27.984 | 28.012 | **27.246** |
| `datetime_passthrough` | 28.004 | 27.969 | 28.090 | **27.398** |
| `datetime_seconds_offset_1024` | 28.004 | 27.898 | 27.949 | **27.352** |
| `datetime_subclass` | 27.941 | 27.996 | 27.906 | **27.336** |
| `datetime_utc_1024` | 27.965 | 27.879 | 28.023 | **27.426** |
| `datetime_utc_1024_omit_microseconds` | 27.910 | 28.023 | 27.949 | **27.367** |
| `datetime_utc_1024_omit_microseconds_utc_z` | 27.969 | 28.000 | 27.938 | **27.406** |
| `datetime_utc_1024_utc_z` | 27.953 | 27.992 | 27.891 | **27.395** |
| `datetime_utc_1024_zero_microseconds` | 28.000 | 27.934 | 27.934 | **27.355** |
| `datetime_utc_16` | 28.016 | 27.961 | 27.863 | **27.340** |
| `datetime_utc_scalar` | 27.957 | 27.895 | 28.000 | **27.410** |
| `dict_control` | 27.953 | 27.914 | 28.000 | **27.320** |
| `list_control` | 27.914 | 27.969 | 27.965 | **27.398** |
| `string_control` | 28.012 | 27.996 | 27.973 | **27.305** |
| `time_1024_omit_microseconds` | 27.895 | 27.895 | 27.934 | **27.371** |
| `time_1024_zero_microseconds` | 27.984 | 27.984 | 27.949 | **27.250** |
| `time_scalar` | 28.031 | 28.039 | 27.902 | **27.402** |
| `uuid_list_control` | 28.020 | 27.906 | 28.105 | **27.316** |
| `uuid_scalar_control` | 27.969 | 28.059 | 27.980 | **27.418** |

Prepared RSS (Linux VmRSS) (MiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 28.012 | **27.969** | 27.988 | 27.406 |
| `time_1024` | **27.895** | 28.031 | 27.902 | 27.398 |
| `time_16` | 27.965 | 27.965 | **27.930** | 27.328 |

RSS with the first result alive (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dataclass_control` | 27.973 | 27.891 | 28.031 | **27.367** |
| `dataclass_dates` | 27.926 | 27.984 | 28.016 | **27.367** |
| `date_1024` | 27.953 | 27.953 | 27.871 | **27.340** |
| `date_1024_options` | 27.969 | 27.984 | 28.016 | **27.465** |
| `date_16` | 27.984 | 27.996 | 27.918 | **27.336** |
| `date_scalar` | 27.965 | 28.008 | 27.918 | **27.355** |
| `datetime_fixed_offset_1024` | 27.953 | 27.984 | 27.910 | **27.352** |
| `datetime_fixed_offset_16` | 27.965 | 27.969 | 27.875 | **27.402** |
| `datetime_fixed_offset_scalar` | 27.887 | 27.910 | 27.949 | **27.348** |
| `datetime_naive_1024` | 27.965 | 28.047 | 27.949 | **27.305** |
| `datetime_naive_1024_naive_utc` | 28.008 | 27.969 | 27.871 | **27.449** |
| `datetime_naive_1024_naive_utc_omit_microseconds` | 27.930 | 28.000 | 28.023 | **27.316** |
| `datetime_naive_1024_naive_utc_omit_microseconds_utc_z` | 28.047 | 27.965 | 27.902 | **27.293** |
| `datetime_naive_1024_naive_utc_z` | 28.047 | 28.020 | 27.914 | **27.352** |
| `datetime_naive_1024_omit_microseconds` | 27.984 | 27.977 | 28.027 | **27.332** |
| `datetime_naive_1024_omit_microseconds_utc_z` | 28.043 | 28.055 | 28.016 | **27.402** |
| `datetime_naive_1024_utc_z` | 28.039 | 27.996 | 28.090 | **27.289** |
| `datetime_naive_1024_zero_microseconds` | 27.891 | 27.984 | 28.027 | **27.465** |
| `datetime_naive_16` | 27.984 | 28.020 | 27.965 | **27.305** |
| `datetime_naive_scalar` | 28.008 | 27.895 | 28.008 | **27.340** |
| `datetime_named_zero_offset_1024` | 28.000 | 27.961 | 28.000 | **27.320** |
| `datetime_negative_offset_1024` | 28.016 | 27.984 | 28.012 | **27.246** |
| `datetime_passthrough` | 28.004 | 27.969 | 28.090 | **27.398** |
| `datetime_seconds_offset_1024` | 28.004 | 27.898 | 27.949 | **27.352** |
| `datetime_subclass` | 27.941 | 27.996 | 27.906 | **27.336** |
| `datetime_utc_1024` | 27.965 | 27.879 | 28.023 | **27.426** |
| `datetime_utc_1024_omit_microseconds` | 27.910 | 28.023 | 27.949 | **27.367** |
| `datetime_utc_1024_omit_microseconds_utc_z` | 27.969 | 28.000 | 27.938 | **27.406** |
| `datetime_utc_1024_utc_z` | 27.953 | 27.992 | 27.891 | **27.395** |
| `datetime_utc_1024_zero_microseconds` | 28.000 | 27.934 | 27.934 | **27.355** |
| `datetime_utc_16` | 28.016 | 27.961 | 27.863 | **27.340** |
| `datetime_utc_scalar` | 27.957 | 27.895 | 28.000 | **27.410** |
| `dict_control` | 27.953 | 27.914 | 28.000 | **27.320** |
| `list_control` | 27.914 | 27.969 | 27.965 | **27.398** |
| `string_control` | 28.012 | 27.996 | 27.973 | **27.305** |
| `time_1024_omit_microseconds` | 27.895 | 27.895 | 27.934 | **27.371** |
| `time_1024_zero_microseconds` | 27.984 | 27.984 | 27.949 | **27.250** |
| `time_scalar` | 28.031 | 28.039 | 27.902 | **27.402** |
| `uuid_list_control` | 28.020 | 27.906 | 28.105 | **27.316** |
| `uuid_scalar_control` | 27.969 | 28.059 | 27.980 | **27.418** |

RSS with the first result alive (Linux VmRSS) (MiB). Different output bytes: bold compares only the three jsonmodem builds. Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `dates_under_dict` | 28.012 | **27.969** | 27.988 | 27.406 |
| `time_1024` | **27.895** | 28.031 | 27.902 | 27.398 |
| `time_16` | 27.965 | 27.965 | **27.930** | 27.328 |
