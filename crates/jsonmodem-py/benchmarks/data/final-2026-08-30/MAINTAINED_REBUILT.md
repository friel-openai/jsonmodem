# Maintained suite: rebuilt control

Rebuilt is a new compilation of unchanged PR #3 source (`b7fe329`).
Final is the changed implementation (`b0f3190`).
The reference is orjson 3.11.9. See [definitions and methods](README.md).

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

## Output

Complete-call latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `small` | 0.409 | 0.423 | **0.265** | 0.266 |
| `medium` | 164.231 | 161.499 | 90.447 | **89.675** |
| `integers` | 114.861 | 113.875 | 44.137 | **43.571** |
| `floats` | 320.498 | 317.733 | 294.300 | **292.536** |
| `strings` | 25.055 | 25.061 | 13.461 | **13.108** |
| `escaped` | 90.942 | 92.317 | 41.698 | **41.428** |
| `long_string` | 12.229 | 12.057 | **9.941** | 10.196 |
| `integers_wide_signed` | **261.009** | 261.395 | 352.847 | 352.426 |
| `integers_wide_unsigned` | 280.584 | **279.302** | 331.972 | 331.052 |
| `scalar_integer` | **0.158** | 0.168 | 0.167 | 0.164 |
| `integers_tiny` | 0.233 | 0.241 | 0.202 | **0.197** |
| `indent_integers` | 144.169 | 142.062 | **83.416** | 83.658 |
| `strict_integers` | 116.003 | 113.798 | 44.365 | **43.614** |
| `sorted_medium` | 260.356 | 254.629 | 130.396 | **130.175** |
| `integer_keys` | 37.240 | 35.987 | 35.129 | **34.904** |
| `dataclasses` | 204.305 | 212.721 | 79.325 | **78.404** |
| `dataclass_single` | 0.946 | 0.951 | 0.265 | **0.262** |
| `dataclass_slots_single` | 1.533 | 1.540 | 0.636 | **0.626** |
| `dataclass_slots` | 735.965 | 751.631 | 409.286 | **384.698** |
| `dataclass_nested` | 590.420 | 538.478 | 197.504 | **195.356** |
| `dataclass_indent` | 227.285 | 224.753 | 107.246 | **106.004** |
| `dataclass_sorted` | 634.351 | 589.341 | **218.522** | 224.268 |
| `dataclass_default` | 288.820 | 289.789 | 129.259 | **126.990** |
| `numpy_int64` | 933.863 | **926.160** | 1,342.727 | 1,330.705 |
| `numpy_float32` | **2,817.598** | 2,817.747 | 3,257.446 | 3,245.291 |
| `late_default` | 9.973 | 9.492 | 3.314 | **2.875** |
| `dataclass_fields8` | 409.247 | 413.993 | 180.446 | **174.484** |
| `dataclass_fields16` | 723.992 | 734.420 | 309.738 | **304.988** |

## Frontend

Complete-call latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads_small` | 0.597 | 0.602 | **0.522** | 0.525 |
| `loads_small_bytearray` | 0.617 | 0.625 | **0.526** | 0.528 |
| `loads_small_memoryview` | 0.685 | 0.678 | **0.527** | 0.529 |
| `loads_small_array_view` | 0.683 | 0.680 | **0.529** | 0.529 |
| `loads_medium` | 380.064 | 374.156 | 245.419 | **243.898** |
| `loads_medium_bytearray` | 371.540 | 376.443 | 247.821 | **243.617** |
| `loads_medium_memoryview` | 370.837 | 377.164 | 246.028 | **244.695** |
| `loads_medium_array_view` | 374.074 | 376.885 | 246.877 | **244.334** |
| `loads_integers` | 280.543 | 282.387 | **187.162** | 187.384 |
| `loads_integers_bytearray` | 281.250 | 283.887 | **186.939** | 187.566 |
| `loads_integers_memoryview` | 280.820 | 283.839 | 187.228 | **187.124** |
| `loads_integers_array_view` | 280.628 | 284.238 | **186.761** | 187.951 |
| `loads_floats` | 485.108 | 490.554 | **276.133** | 278.540 |
| `loads_floats_bytearray` | 491.256 | 496.232 | **276.918** | 276.961 |
| `loads_floats_memoryview` | 490.907 | 497.320 | **275.720** | 276.919 |
| `loads_floats_array_view` | 491.401 | 498.789 | **276.218** | 277.469 |
| `loads_strings` | 47.658 | 47.901 | 36.854 | **36.545** |
| `loads_strings_bytearray` | 48.876 | 48.872 | **36.732** | 36.992 |
| `loads_strings_memoryview` | 48.580 | 49.091 | **36.678** | 36.789 |
| `loads_strings_array_view` | 48.657 | 49.122 | **36.708** | 36.845 |
| `loads_escaped` | 247.627 | 248.596 | **143.728** | 143.964 |
| `loads_escaped_bytearray` | 247.752 | 252.750 | **144.420** | 144.896 |
| `loads_escaped_memoryview` | 246.597 | 252.199 | **143.828** | 144.101 |
| `loads_escaped_array_view` | 246.687 | 251.647 | 144.986 | **144.814** |
| `loads_long_string` | **18.940** | 21.803 | 92.609 | 92.796 |
| `loads_long_string_bytearray` | **23.515** | 26.179 | 92.628 | 93.308 |
| `loads_long_string_memoryview` | **23.657** | 26.004 | 92.544 | 93.024 |
| `loads_long_string_array_view` | **23.754** | 26.038 | 92.520 | 93.246 |
| `dumps_root_empty` | 0.151 | **0.145** | 0.167 | 0.167 |
| `loads_root_empty` | 0.132 | 0.146 | **0.092** | 0.092 |
| `dumps_root_tiny` | **0.158** | 0.167 | 0.166 | 0.168 |
| `loads_root_tiny` | **0.161** | 0.170 | 0.197 | 0.195 |
| `dumps_root_below_threshold` | 0.260 | 0.278 | **0.219** | 0.219 |
| `loads_root_below_threshold` | **0.208** | 0.233 | 0.272 | 0.274 |
| `dumps_root_at_threshold` | **0.163** | 0.175 | 0.220 | 0.224 |
| `loads_root_at_threshold` | **0.204** | 0.242 | 0.274 | 0.273 |
| `dumps_root_medium` | 0.538 | 0.550 | 0.521 | **0.521** |
| `loads_root_medium` | **0.773** | 0.855 | 1.468 | 1.463 |
| `dumps_root_long` | 11.080 | 11.241 | 9.266 | **9.223** |
| `loads_root_long` | **17.430** | 19.870 | 84.484 | 84.860 |
| `dumps_root_early_quote` | 13.208 | 13.937 | **9.215** | 9.283 |
| `loads_root_early_quote` | **22.893** | 25.535 | 89.150 | 89.905 |
| `dumps_root_late_quote` | 13.059 | 13.741 | 9.254 | **9.250** |
| `loads_root_late_quote` | **22.740** | 25.315 | 84.525 | 85.135 |
| `dumps_root_dense_escapes` | 228.069 | 228.886 | 189.257 | **189.244** |
| `loads_root_dense_escapes` | 266.226 | **119.510** | 127.220 | 128.204 |
| `dumps_root_latin1` | 11.551 | 11.814 | **8.609** | 8.690 |
| `loads_root_latin1` | 98.814 | 99.032 | **93.631** | 93.832 |
| `dumps_root_bmp` | 11.507 | 11.898 | 8.626 | **8.608** |
| `loads_root_bmp` | 97.794 | 97.902 | **82.198** | 82.757 |
| `dumps_root_non_bmp` | 11.885 | 12.003 | 8.598 | **8.585** |
| `loads_root_non_bmp` | 86.653 | 86.860 | **65.972** | 66.146 |
| `dumps_root_append_newline` | 11.157 | 11.286 | **9.293** | 9.321 |
| `dumps_root_indent` | 11.167 | 11.301 | **9.319** | 9.326 |
| `loads_escaped_values` | 64.744 | 65.387 | 34.421 | **34.051** |
| `loads_unicode_escapes` | 153.352 | 142.358 | 45.886 | **45.590** |
| `loads_repeated_escaped_keys` | 128.035 | 124.701 | 87.323 | **87.200** |
| `loads_unique_escaped_keys` | 143.676 | 146.487 | **36.730** | 36.872 |

## Numbers

Complete-call latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads_small` | 0.338 | 0.323 | **0.267** | 0.267 |
| `loads_medium` | 301.058 | 308.246 | **193.377** | 193.643 |
| `loads_integers` | 279.532 | 285.186 | **185.822** | 186.234 |
| `loads_random_small` | 340.713 | 340.214 | 240.828 | **240.161** |
| `loads_wide_signed` | 465.280 | 462.559 | **351.092** | 351.162 |
| `loads_wide_unsigned` | 403.299 | 411.934 | **267.984** | 274.158 |
| `loads_mixed_integers` | 476.542 | 482.869 | **347.486** | 349.984 |
| `loads_tiny_integers` | 0.215 | 0.209 | **0.201** | 0.201 |
| `loads_scalar_integer` | 0.085 | **0.080** | 0.115 | 0.115 |
| `loads_floats` | 487.543 | 492.312 | **277.121** | 278.585 |
| `loads_float_bits` | 722.796 | 731.527 | 430.224 | **427.418** |
| `loads_overflow_integers` | 942.745 | 997.068 | **660.997** | 661.040 |
| `loads_long_fractions` | 749.412 | 750.459 | **440.484** | 440.987 |
| `loads_zero_forms` | 0.351 | 0.345 | **0.231** | 0.234 |
| `dumps_small` | 0.203 | 0.204 | **0.129** | 0.130 |
| `dumps_medium` | 143.021 | 142.132 | **79.303** | 79.584 |
| `dumps_integers` | 112.935 | 112.970 | **42.928** | 42.994 |
| `dumps_random_small` | 150.913 | 151.256 | 77.143 | **75.007** |
| `dumps_wide_signed` | 265.164 | **263.998** | 357.140 | 358.501 |
| `dumps_wide_unsigned` | 283.968 | **282.169** | 335.858 | 335.695 |
| `dumps_mixed_integers` | 308.881 | **306.472** | 358.348 | 357.920 |
| `dumps_tiny_integers` | 0.142 | 0.142 | 0.115 | **0.115** |
| `dumps_scalar_integer` | **0.076** | 0.076 | 0.089 | 0.089 |
| `dumps_floats` | 323.970 | 321.609 | **299.449** | 303.215 |
| `dumps_float_bits` | 392.705 | 400.389 | 307.400 | **306.975** |

## Strings

Complete-call latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads/short_plain/bytes` | 0.093 | **0.086** | 0.131 | 0.136 |
| `loads/short_plain/bytearray` | **0.106** | 0.107 | 0.141 | 0.144 |
| `loads/short_plain/memoryview` | 0.140 | 0.156 | **0.134** | 0.140 |
| `loads/short_plain/array_view` | 0.139 | 0.154 | **0.134** | 0.138 |
| `dumps/short_plain/object` | **0.079** | 0.083 | 0.086 | 0.086 |
| `loads/short_escaped/bytes` | 0.136 | 0.132 | **0.132** | 0.134 |
| `loads/short_escaped/bytearray` | 0.153 | 0.147 | **0.139** | 0.144 |
| `loads/short_escaped/memoryview` | 0.219 | 0.220 | **0.136** | 0.136 |
| `loads/short_escaped/array_view` | 0.218 | 0.219 | **0.136** | 0.137 |
| `dumps/short_escaped/object` | **0.086** | 0.098 | 0.090 | 0.090 |
| `loads/plain_values/bytes` | 47.283 | 47.874 | **36.454** | 36.711 |
| `loads/plain_values/bytearray` | 48.265 | 49.000 | **36.504** | 36.719 |
| `loads/plain_values/memoryview` | 48.266 | 49.094 | **36.529** | 36.750 |
| `loads/plain_values/array_view` | 48.068 | 48.857 | **36.455** | 36.689 |
| `dumps/plain_values/object` | 24.140 | 24.211 | 12.650 | **12.640** |
| `loads/escaped_values/bytes` | 69.731 | 71.062 | 37.740 | **37.731** |
| `loads/escaped_values/bytearray` | 70.480 | 71.236 | **37.715** | 37.821 |
| `loads/escaped_values/memoryview` | 70.305 | 71.672 | **37.618** | 37.908 |
| `loads/escaped_values/array_view` | 70.771 | 71.621 | **37.891** | 38.080 |
| `dumps/escaped_values/object` | 33.534 | 33.296 | **23.303** | 23.692 |
| `loads/unicode_escapes/bytes` | 155.190 | 154.863 | **51.650** | 52.014 |
| `loads/unicode_escapes/bytearray` | 156.437 | 155.669 | 52.934 | **51.486** |
| `loads/unicode_escapes/memoryview` | 158.593 | 156.111 | **51.740** | 51.850 |
| `loads/unicode_escapes/array_view` | 159.138 | 156.063 | 51.878 | **51.548** |
| `dumps/unicode_escapes/object` | 22.250 | 22.201 | **11.173** | 11.210 |
| `loads/escaped_keys/bytes` | 332.415 | 335.475 | **169.805** | 170.804 |
| `loads/escaped_keys/bytearray` | 335.562 | 337.876 | **170.371** | 170.678 |
| `loads/escaped_keys/memoryview` | 335.478 | 339.818 | **170.800** | 171.388 |
| `loads/escaped_keys/array_view` | 333.486 | 337.214 | 171.479 | **171.316** |
| `dumps/escaped_keys/object` | 103.573 | 103.240 | 46.395 | **46.118** |
| `loads/unique_keys/bytes` | 165.167 | 160.743 | 48.529 | **47.725** |
| `loads/unique_keys/bytearray` | 164.067 | 161.352 | 47.605 | **47.541** |
| `loads/unique_keys/memoryview` | 165.132 | 161.689 | 48.142 | **47.595** |
| `loads/unique_keys/array_view` | 166.437 | 162.316 | 48.046 | **47.575** |
| `dumps/unique_keys/object` | 35.312 | 34.727 | **11.888** | 12.045 |
| `loads/long_plain/bytes` | **19.534** | 22.203 | 94.591 | 94.942 |
| `loads/long_plain/bytearray` | **24.744** | 26.764 | 94.967 | 95.550 |
| `loads/long_plain/memoryview` | **24.415** | 26.788 | 94.814 | 94.958 |
| `loads/long_plain/array_view` | **24.448** | 26.880 | 95.277 | 95.647 |
| `dumps/long_plain/object` | 12.427 | 12.419 | 10.437 | **10.387** |
| `loads/long_escaped/bytes` | 93.597 | **60.975** | 99.742 | 100.437 |
| `loads/long_escaped/bytearray` | 97.531 | **64.615** | 99.729 | 100.447 |
| `loads/long_escaped/memoryview` | 97.571 | **64.835** | 99.626 | 100.216 |
| `loads/long_escaped/array_view` | 97.230 | **64.514** | 99.636 | 100.093 |
| `dumps/long_escaped/object` | 70.952 | 72.485 | **50.832** | 53.106 |
| `loads/late_escape/bytes` | **25.641** | 28.340 | 95.284 | 94.910 |
| `loads/late_escape/bytearray` | **76.484** | 78.687 | 94.733 | 95.288 |
| `loads/late_escape/memoryview` | **76.294** | 78.982 | 95.202 | 94.855 |
| `loads/late_escape/array_view` | **76.322** | 78.668 | 95.220 | 95.062 |
| `dumps/late_escape/object` | 15.449 | 15.067 | 10.306 | **10.192** |
| `loads/medium/bytes` | 370.256 | 378.743 | 250.477 | **249.069** |
| `loads/medium/bytearray` | 378.552 | 389.256 | 249.371 | **248.630** |
| `loads/medium/memoryview` | 380.235 | 383.308 | 248.882 | **248.395** |
| `loads/medium/array_view` | 382.060 | 381.852 | 250.341 | **249.067** |
| `dumps/medium/object` | 163.280 | 162.514 | 90.080 | **89.970** |
| `loads/integers/bytes` | 278.334 | 282.870 | 186.825 | **186.558** |
| `loads/integers/bytearray` | 280.477 | 286.348 | **187.830** | 188.336 |
| `loads/integers/memoryview` | 280.480 | 284.253 | **186.038** | 186.327 |
| `loads/integers/array_view` | 281.941 | 284.431 | **187.280** | 187.443 |
| `dumps/integers/object` | 114.113 | 114.578 | **44.140** | 44.223 |
