# Maintained suite: original control

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

## Output

Complete-call latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `small` | 0.417 | 0.377 | 0.276 | **0.269** |
| `medium` | 161.531 | 145.572 | **89.681** | 90.233 |
| `integers` | 113.766 | 108.401 | **43.768** | 43.971 |
| `floats` | 317.315 | 311.379 | **291.992** | 293.386 |
| `strings` | 24.678 | 22.804 | **13.108** | 13.390 |
| `escaped` | 91.942 | 89.258 | **40.578** | 41.066 |
| `long_string` | 12.130 | 12.176 | 10.320 | **10.051** |
| `integers_wide_signed` | 260.806 | **245.118** | 352.419 | 354.180 |
| `integers_wide_unsigned` | 279.418 | **197.182** | 331.666 | 331.769 |
| `scalar_integer` | 0.167 | 0.169 | **0.164** | 0.167 |
| `integers_tiny` | 0.238 | 0.248 | **0.199** | 0.203 |
| `indent_integers` | 141.860 | 138.089 | **82.819** | 84.837 |
| `strict_integers` | 113.435 | 114.498 | **43.960** | 44.285 |
| `sorted_medium` | 256.133 | 285.742 | **129.586** | 129.707 |
| `integer_keys` | 36.204 | 36.286 | 35.168 | **35.088** |
| `dataclasses` | 211.663 | 196.544 | **78.459** | 82.138 |
| `dataclass_single` | 0.948 | 0.949 | **0.263** | 0.270 |
| `dataclass_slots_single` | 1.537 | 1.530 | **0.630** | 0.648 |
| `dataclass_slots` | 743.647 | 737.500 | **403.291** | 416.693 |
| `dataclass_nested` | 528.931 | 510.636 | **197.390** | 201.362 |
| `dataclass_indent` | 226.109 | 218.474 | **104.641** | 109.113 |
| `dataclass_sorted` | 578.936 | 564.183 | **218.352** | 224.907 |
| `dataclass_default` | 295.938 | 269.844 | **130.906** | 136.878 |
| `numpy_int64` | **921.443** | 927.354 | 1,336.031 | 1,335.482 |
| `numpy_float32` | **2,796.215** | 2,797.818 | 3,242.427 | 3,248.982 |
| `late_default` | 9.773 | 10.362 | **2.849** | 3.180 |
| `dataclass_fields8` | 419.075 | 419.946 | 174.495 | **174.344** |
| `dataclass_fields16` | 736.513 | 773.803 | **305.101** | 305.869 |

## Frontend

Complete-call latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads_small` | 0.600 | 0.566 | **0.525** | 0.529 |
| `loads_small_bytearray` | 0.624 | 0.594 | **0.529** | 0.529 |
| `loads_small_memoryview` | 0.673 | 0.671 | **0.529** | 0.534 |
| `loads_small_array_view` | 0.673 | 0.672 | 0.531 | **0.530** |
| `loads_medium` | 371.670 | 356.936 | **242.463** | 243.701 |
| `loads_medium_bytearray` | 376.324 | 359.941 | 246.340 | **243.978** |
| `loads_medium_memoryview` | 375.512 | 365.813 | 244.920 | **244.307** |
| `loads_medium_array_view` | 377.369 | 365.195 | 245.143 | **244.030** |
| `loads_integers` | 283.732 | 252.626 | **187.673** | 189.708 |
| `loads_integers_bytearray` | 285.124 | 254.424 | **186.193** | 191.559 |
| `loads_integers_memoryview` | 283.782 | 252.955 | **188.049** | 189.077 |
| `loads_integers_array_view` | 283.883 | 253.834 | **187.502** | 189.501 |
| `loads_floats` | 491.959 | 458.787 | **278.411** | 279.420 |
| `loads_floats_bytearray` | 497.824 | 469.715 | **278.033** | 279.373 |
| `loads_floats_memoryview` | 500.974 | 467.511 | **277.651** | 279.031 |
| `loads_floats_array_view` | 497.427 | 466.295 | **277.874** | 280.238 |
| `loads_strings` | 48.111 | 38.684 | **36.588** | 36.765 |
| `loads_strings_bytearray` | 49.315 | 39.443 | **36.766** | 36.857 |
| `loads_strings_memoryview` | 49.251 | 39.941 | **36.633** | 37.037 |
| `loads_strings_array_view` | 49.953 | 39.525 | 36.958 | **36.658** |
| `loads_escaped` | 248.797 | 247.239 | **142.711** | 144.018 |
| `loads_escaped_bytearray` | 252.536 | 249.616 | **143.789** | 145.046 |
| `loads_escaped_memoryview` | 251.896 | 249.934 | 144.113 | **144.101** |
| `loads_escaped_array_view` | 251.685 | 249.674 | 143.958 | **143.575** |
| `loads_long_string` | 21.713 | **16.836** | 92.373 | 92.950 |
| `loads_long_string_bytearray` | 25.791 | **21.318** | 92.682 | 92.999 |
| `loads_long_string_memoryview` | 26.223 | **21.649** | 92.318 | 93.698 |
| `loads_long_string_array_view` | 26.261 | **21.502** | 92.317 | 93.085 |
| `dumps_root_empty` | 0.146 | **0.142** | 0.166 | 0.166 |
| `loads_root_empty` | 0.147 | 0.139 | 0.093 | **0.092** |
| `dumps_root_tiny` | 0.167 | **0.152** | 0.165 | 0.167 |
| `loads_root_tiny` | 0.170 | **0.159** | 0.198 | 0.198 |
| `dumps_root_below_threshold` | 0.280 | 0.255 | **0.219** | 0.220 |
| `loads_root_below_threshold` | 0.234 | **0.195** | 0.275 | 0.273 |
| `dumps_root_at_threshold` | 0.174 | **0.161** | 0.221 | 0.221 |
| `loads_root_at_threshold` | 0.245 | **0.196** | 0.276 | 0.279 |
| `dumps_root_medium` | 0.550 | 0.531 | **0.519** | 0.540 |
| `loads_root_medium` | 0.850 | **0.683** | 1.464 | 1.464 |
| `dumps_root_long` | 11.072 | 11.289 | **9.174** | 9.386 |
| `loads_root_long` | 19.851 | **15.404** | 84.658 | 84.823 |
| `dumps_root_early_quote` | 13.544 | 13.786 | **9.250** | 9.372 |
| `loads_root_early_quote` | 25.334 | **19.354** | 89.529 | 90.064 |
| `dumps_root_late_quote` | 13.540 | 13.593 | **9.185** | 9.340 |
| `loads_root_late_quote` | 25.253 | **19.214** | 84.584 | 85.016 |
| `dumps_root_dense_escapes` | 227.838 | **84.842** | 189.242 | 189.379 |
| `loads_root_dense_escapes` | **117.269** | 121.617 | 127.332 | 127.604 |
| `dumps_root_latin1` | 11.687 | 11.780 | **8.553** | 8.590 |
| `loads_root_latin1` | 98.689 | 98.508 | **93.679** | 93.800 |
| `dumps_root_bmp` | 12.042 | 11.865 | 8.708 | **8.632** |
| `loads_root_bmp` | 97.764 | 97.920 | 82.497 | **82.284** |
| `dumps_root_non_bmp` | 12.023 | 11.769 | 8.630 | **8.552** |
| `loads_root_non_bmp` | 86.769 | 86.667 | 66.123 | **66.080** |
| `dumps_root_append_newline` | 11.180 | 11.247 | **9.254** | 9.450 |
| `dumps_root_indent` | 11.185 | 11.239 | **9.270** | 9.463 |
| `loads_escaped_values` | 65.799 | 54.256 | 34.341 | **34.059** |
| `loads_unicode_escapes` | 142.932 | 136.731 | **45.659** | 45.882 |
| `loads_repeated_escaped_keys` | 123.977 | 122.713 | **86.853** | 87.515 |
| `loads_unique_escaped_keys` | 145.312 | 143.339 | **36.646** | 36.870 |

## Numbers

Complete-call latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads_small` | 0.326 | 0.306 | 0.268 | **0.268** |
| `loads_medium` | 309.993 | 292.323 | 194.577 | **194.217** |
| `loads_integers` | 287.847 | 254.142 | **186.770** | 188.120 |
| `loads_random_small` | 343.515 | 310.942 | **241.100** | 241.570 |
| `loads_wide_signed` | 468.426 | 435.082 | 354.908 | **353.479** |
| `loads_wide_unsigned` | 411.999 | 382.499 | **271.701** | 272.851 |
| `loads_mixed_integers` | 483.995 | 440.270 | 350.063 | **347.023** |
| `loads_tiny_integers` | 0.210 | **0.199** | 0.201 | 0.202 |
| `loads_scalar_integer` | **0.080** | 0.085 | 0.116 | 0.117 |
| `loads_floats` | 493.652 | 461.294 | 278.357 | **278.115** |
| `loads_float_bits` | 732.216 | 693.457 | 430.902 | **428.997** |
| `loads_overflow_integers` | 996.227 | 914.177 | **662.201** | 663.420 |
| `loads_long_fractions` | 746.916 | 723.488 | **439.816** | 443.263 |
| `loads_zero_forms` | 0.344 | 0.319 | 0.237 | **0.237** |
| `dumps_small` | 0.207 | 0.169 | 0.130 | **0.129** |
| `dumps_medium` | 142.342 | 126.217 | 79.630 | **79.551** |
| `dumps_integers` | 113.712 | 107.350 | **42.947** | 43.076 |
| `dumps_random_small` | 152.134 | 157.289 | **74.328** | 74.557 |
| `dumps_wide_signed` | 269.746 | **248.527** | 357.902 | 357.820 |
| `dumps_wide_unsigned` | 287.464 | **201.771** | 336.215 | 335.384 |
| `dumps_mixed_integers` | 308.330 | **254.546** | 358.497 | 358.103 |
| `dumps_tiny_integers` | 0.146 | 0.147 | **0.115** | 0.115 |
| `dumps_scalar_integer` | 0.076 | **0.076** | 0.089 | 0.089 |
| `dumps_floats` | 324.088 | 318.913 | **297.428** | 298.017 |
| `dumps_float_bits` | 396.891 | 399.607 | **307.517** | 307.998 |

## Strings

Complete-call latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads/short_plain/bytes` | **0.084** | 0.093 | 0.133 | 0.137 |
| `loads/short_plain/bytearray` | **0.101** | 0.108 | 0.147 | 0.145 |
| `loads/short_plain/memoryview` | 0.155 | 0.162 | 0.139 | **0.139** |
| `loads/short_plain/array_view` | 0.154 | 0.163 | **0.137** | 0.139 |
| `dumps/short_plain/object` | 0.082 | **0.075** | 0.086 | 0.086 |
| `loads/short_escaped/bytes` | 0.134 | **0.130** | 0.132 | 0.132 |
| `loads/short_escaped/bytearray` | 0.145 | 0.147 | **0.144** | 0.144 |
| `loads/short_escaped/memoryview` | 0.219 | 0.220 | **0.136** | 0.136 |
| `loads/short_escaped/array_view` | 0.219 | 0.221 | **0.136** | 0.136 |
| `dumps/short_escaped/object` | 0.098 | **0.086** | 0.090 | 0.090 |
| `loads/plain_values/bytes` | 47.737 | 38.543 | 36.563 | **36.502** |
| `loads/plain_values/bytearray` | 48.580 | 39.415 | **36.367** | 36.619 |
| `loads/plain_values/memoryview` | 48.913 | 39.395 | 36.539 | **36.505** |
| `loads/plain_values/array_view` | 48.791 | 39.477 | 36.460 | **36.440** |
| `dumps/plain_values/object` | 24.194 | 21.765 | 12.642 | **12.635** |
| `loads/escaped_values/bytes` | 71.082 | 66.679 | **37.752** | 38.065 |
| `loads/escaped_values/bytearray` | 71.570 | 67.072 | **37.643** | 38.094 |
| `loads/escaped_values/memoryview` | 71.427 | 66.849 | **37.606** | 37.901 |
| `loads/escaped_values/array_view` | 71.941 | 66.273 | **37.942** | 38.022 |
| `dumps/escaped_values/object` | 33.354 | 31.136 | 23.307 | **22.035** |
| `loads/unicode_escapes/bytes` | 155.185 | 142.962 | 51.813 | **51.575** |
| `loads/unicode_escapes/bytearray` | 156.064 | 145.487 | **51.496** | 51.883 |
| `loads/unicode_escapes/memoryview` | 156.371 | 145.327 | **51.875** | 51.984 |
| `loads/unicode_escapes/array_view` | 155.333 | 144.496 | **51.692** | 51.871 |
| `dumps/unicode_escapes/object` | 22.088 | 21.537 | 11.184 | **11.167** |
| `loads/escaped_keys/bytes` | 338.127 | 311.811 | 171.123 | **169.994** |
| `loads/escaped_keys/bytearray` | 338.789 | 314.177 | 170.364 | **170.336** |
| `loads/escaped_keys/memoryview` | 338.888 | 314.718 | 171.699 | **170.064** |
| `loads/escaped_keys/array_view` | 336.103 | 313.973 | 171.190 | **171.079** |
| `dumps/escaped_keys/object` | 104.811 | 91.450 | **46.281** | 46.441 |
| `loads/unique_keys/bytes` | 161.414 | 158.746 | **47.849** | 47.963 |
| `loads/unique_keys/bytearray` | 161.610 | 159.171 | **47.800** | 47.834 |
| `loads/unique_keys/memoryview` | 161.983 | 160.619 | **47.736** | 47.987 |
| `loads/unique_keys/array_view` | 162.455 | 159.902 | **47.803** | 48.113 |
| `dumps/unique_keys/object` | 34.708 | 28.938 | **11.877** | 11.985 |
| `loads/long_plain/bytes` | 22.111 | **17.105** | 95.342 | 96.005 |
| `loads/long_plain/bytearray` | 26.606 | **22.322** | 95.615 | 95.642 |
| `loads/long_plain/memoryview` | 26.675 | **22.271** | 95.138 | 95.756 |
| `loads/long_plain/array_view` | 26.922 | **22.526** | 95.665 | 95.553 |
| `dumps/long_plain/object` | 12.392 | 12.438 | **10.403** | 10.429 |
| `loads/long_escaped/bytes` | 61.127 | **58.048** | 100.204 | 101.232 |
| `loads/long_escaped/bytearray` | 64.855 | **62.413** | 99.835 | 100.635 |
| `loads/long_escaped/memoryview` | 64.949 | **62.232** | 100.087 | 100.874 |
| `loads/long_escaped/array_view` | 64.858 | **62.357** | 100.170 | 100.675 |
| `dumps/long_escaped/object` | 73.379 | **47.998** | 53.087 | 50.625 |
| `loads/late_escape/bytes` | 28.269 | **22.304** | 95.185 | 95.617 |
| `loads/late_escape/bytearray` | 78.999 | **73.033** | 95.493 | 95.440 |
| `loads/late_escape/memoryview` | 79.058 | **73.553** | 95.241 | 95.614 |
| `loads/late_escape/array_view` | 79.461 | **73.382** | 95.289 | 95.545 |
| `dumps/late_escape/object` | 15.310 | 16.024 | 10.244 | **10.203** |
| `loads/medium/bytes` | 381.508 | 367.587 | 249.759 | **249.757** |
| `loads/medium/bytearray` | 396.361 | 363.392 | **249.250** | 253.484 |
| `loads/medium/memoryview` | 388.109 | 361.773 | 249.847 | **248.875** |
| `loads/medium/array_view` | 387.240 | 363.508 | **250.883** | 251.390 |
| `dumps/medium/object` | 162.774 | 146.413 | 90.498 | **90.248** |
| `loads/integers/bytes` | 283.571 | 254.834 | 188.571 | **188.369** |
| `loads/integers/bytearray` | 287.278 | 255.281 | 190.514 | **188.495** |
| `loads/integers/memoryview` | 284.894 | 256.305 | **188.081** | 189.309 |
| `loads/integers/array_view` | 286.495 | 257.366 | **189.684** | 190.178 |
| `dumps/integers/object` | 114.523 | 108.176 | **44.162** | 44.216 |
