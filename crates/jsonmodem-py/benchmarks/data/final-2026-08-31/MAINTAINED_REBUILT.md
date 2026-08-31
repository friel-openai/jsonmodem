# Maintained suite: rebuilt control

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

## Output

Complete-call latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `small` | 0.421 | 0.382 | 0.271 | **0.269** |
| `medium` | 162.920 | 145.985 | 89.900 | **89.716** |
| `integers` | 113.926 | 108.580 | 44.123 | **43.982** |
| `floats` | 320.314 | 315.398 | **293.162** | 293.286 |
| `strings` | 25.378 | 22.474 | 13.560 | **13.368** |
| `escaped` | 92.212 | 89.879 | 41.956 | **40.407** |
| `long_string` | 12.237 | 12.206 | **10.094** | 10.117 |
| `integers_wide_signed` | 265.973 | **246.721** | 353.258 | 354.256 |
| `integers_wide_unsigned` | 281.964 | **198.774** | 331.804 | 331.388 |
| `scalar_integer` | 0.167 | 0.169 | **0.164** | 0.165 |
| `integers_tiny` | 0.239 | 0.249 | **0.198** | 0.200 |
| `indent_integers` | 142.160 | 135.600 | 83.843 | **82.881** |
| `strict_integers` | 113.841 | 114.666 | 44.400 | **43.955** |
| `sorted_medium` | 257.878 | 286.214 | **130.107** | 130.122 |
| `integer_keys` | 36.264 | 36.378 | 35.269 | **35.136** |
| `dataclasses` | 214.289 | 199.357 | 79.321 | **79.055** |
| `dataclass_single` | 0.960 | 0.943 | 0.266 | **0.265** |
| `dataclass_slots_single` | 1.550 | 1.545 | **0.628** | 0.632 |
| `dataclass_slots` | 737.244 | 748.161 | **396.577** | 399.232 |
| `dataclass_nested` | 583.760 | 516.109 | **196.582** | 198.429 |
| `dataclass_indent` | 230.592 | 216.920 | 106.565 | **105.579** |
| `dataclass_sorted` | 637.104 | 561.219 | **216.993** | 218.220 |
| `dataclass_default` | 322.132 | 266.349 | **129.398** | 130.983 |
| `numpy_int64` | 931.845 | **929.856** | 1,342.563 | 1,338.429 |
| `numpy_float32` | 2,821.577 | **2,816.111** | 3,263.125 | 3,253.834 |
| `late_default` | 9.879 | 10.349 | 3.304 | **3.176** |
| `dataclass_fields8` | 425.949 | 418.367 | 181.194 | **173.968** |
| `dataclass_fields16` | 748.648 | 780.397 | **308.101** | 310.927 |

## Frontend

Complete-call latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads_small` | 0.602 | 0.564 | **0.520** | 0.526 |
| `loads_small_bytearray` | 0.621 | 0.590 | **0.525** | 0.528 |
| `loads_small_memoryview` | 0.678 | 0.669 | **0.526** | 0.528 |
| `loads_small_array_view` | 0.677 | 0.671 | **0.525** | 0.542 |
| `loads_medium` | 374.670 | 357.377 | 244.395 | **243.645** |
| `loads_medium_bytearray` | 386.627 | 361.545 | 244.662 | **244.294** |
| `loads_medium_memoryview` | 376.194 | 364.433 | 246.477 | **244.763** |
| `loads_medium_array_view` | 376.225 | 364.330 | **244.992** | 246.979 |
| `loads_integers` | 282.874 | 251.221 | **187.118** | 187.401 |
| `loads_integers_bytearray` | 285.807 | 253.108 | 187.259 | **186.618** |
| `loads_integers_memoryview` | 283.962 | 254.862 | **187.261** | 188.306 |
| `loads_integers_array_view` | 284.440 | 253.169 | **187.500** | 188.500 |
| `loads_floats` | 492.779 | 457.493 | 278.125 | **277.684** |
| `loads_floats_bytearray` | 496.431 | 467.549 | **277.192** | 278.213 |
| `loads_floats_memoryview` | 501.094 | 466.051 | **277.824** | 280.032 |
| `loads_floats_array_view` | 498.964 | 465.186 | **276.991** | 278.939 |
| `loads_strings` | 47.962 | 38.449 | **36.621** | 36.654 |
| `loads_strings_bytearray` | 49.121 | 39.401 | 36.689 | **36.606** |
| `loads_strings_memoryview` | 49.014 | 39.576 | 36.664 | **36.657** |
| `loads_strings_array_view` | 49.128 | 39.765 | **36.538** | 37.319 |
| `loads_escaped` | 260.036 | 246.514 | **142.275** | 144.332 |
| `loads_escaped_bytearray` | 256.920 | 248.339 | 144.349 | **143.049** |
| `loads_escaped_memoryview` | 250.768 | 247.992 | 145.123 | **142.984** |
| `loads_escaped_array_view` | 250.195 | 249.455 | **143.252** | 143.735 |
| `loads_long_string` | 21.798 | **16.774** | 92.843 | 92.734 |
| `loads_long_string_bytearray` | 26.824 | **21.744** | 93.121 | 93.005 |
| `loads_long_string_memoryview` | 26.480 | **21.884** | 92.935 | 92.736 |
| `loads_long_string_array_view` | 26.579 | **21.863** | 92.762 | 92.813 |
| `dumps_root_empty` | 0.146 | **0.141** | 0.167 | 0.168 |
| `loads_root_empty` | 0.148 | 0.137 | 0.093 | **0.092** |
| `dumps_root_tiny` | 0.167 | **0.154** | 0.166 | 0.167 |
| `loads_root_tiny` | 0.170 | **0.158** | 0.197 | 0.199 |
| `dumps_root_below_threshold` | 0.279 | 0.257 | **0.219** | 0.221 |
| `loads_root_below_threshold` | 0.233 | **0.197** | 0.272 | 0.276 |
| `dumps_root_at_threshold` | 0.172 | **0.162** | 0.221 | 0.221 |
| `loads_root_at_threshold` | 0.243 | **0.198** | 0.272 | 0.273 |
| `dumps_root_medium` | 0.540 | 0.529 | **0.517** | 0.537 |
| `loads_root_medium` | 0.855 | **0.682** | 1.462 | 1.471 |
| `dumps_root_long` | 11.141 | 11.210 | **9.239** | 9.491 |
| `loads_root_long` | 19.823 | **15.379** | 84.868 | 85.010 |
| `dumps_root_early_quote` | 14.030 | 13.966 | **9.179** | 9.335 |
| `loads_root_early_quote` | 25.458 | **19.445** | 89.894 | 89.940 |
| `dumps_root_late_quote` | 13.926 | 13.946 | **9.229** | 9.393 |
| `loads_root_late_quote` | 25.277 | **19.423** | 84.885 | 84.884 |
| `dumps_root_dense_escapes` | 229.494 | **85.211** | 189.213 | 189.519 |
| `loads_root_dense_escapes` | **118.591** | 120.604 | 127.454 | 127.819 |
| `dumps_root_latin1` | 11.507 | 11.447 | **8.631** | 8.661 |
| `loads_root_latin1` | 98.488 | 98.867 | 93.934 | **93.906** |
| `dumps_root_bmp` | 11.683 | 11.666 | **8.617** | 8.636 |
| `loads_root_bmp` | 97.713 | 98.237 | **82.501** | 82.561 |
| `dumps_root_non_bmp` | 11.928 | 11.228 | 8.569 | **8.519** |
| `loads_root_non_bmp` | 86.776 | 86.819 | 66.367 | **66.109** |
| `dumps_root_append_newline` | 11.200 | 11.208 | **9.276** | 9.411 |
| `dumps_root_indent` | 11.182 | 11.198 | **9.286** | 9.429 |
| `loads_escaped_values` | 65.781 | 54.463 | **34.266** | 34.679 |
| `loads_unicode_escapes` | 142.866 | 136.609 | **45.643** | 45.986 |
| `loads_repeated_escaped_keys` | 125.385 | 122.371 | **87.166** | 87.446 |
| `loads_unique_escaped_keys` | 145.301 | 143.036 | 36.935 | **36.870** |

## Numbers

Complete-call latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads_small` | 0.322 | 0.308 | **0.266** | 0.267 |
| `loads_medium` | 312.661 | 291.691 | **194.165** | 194.620 |
| `loads_integers` | 284.090 | 253.922 | **187.123** | 188.759 |
| `loads_random_small` | 339.757 | 309.973 | **240.534** | 243.696 |
| `loads_wide_signed` | 464.528 | 428.238 | 354.848 | **349.659** |
| `loads_wide_unsigned` | 413.829 | 378.618 | 273.532 | **273.186** |
| `loads_mixed_integers` | 481.452 | 437.138 | 347.852 | **347.642** |
| `loads_tiny_integers` | 0.208 | **0.197** | 0.200 | 0.201 |
| `loads_scalar_integer` | **0.080** | 0.083 | 0.116 | 0.116 |
| `loads_floats` | 491.229 | 459.343 | 277.507 | **275.985** |
| `loads_float_bits` | 734.893 | 690.399 | 428.983 | **427.358** |
| `loads_overflow_integers` | 993.355 | 910.751 | **660.076** | 661.005 |
| `loads_long_fractions` | 754.231 | 721.269 | **440.149** | 441.041 |
| `loads_zero_forms` | 0.347 | 0.318 | 0.235 | **0.234** |
| `dumps_small` | 0.238 | 0.167 | 0.129 | **0.129** |
| `dumps_medium` | 141.626 | 126.123 | 79.531 | **79.249** |
| `dumps_integers` | 112.799 | 107.349 | **42.875** | 42.974 |
| `dumps_random_small` | 151.450 | 158.279 | 76.597 | **74.567** |
| `dumps_wide_signed` | 269.926 | **252.540** | 357.516 | 357.712 |
| `dumps_wide_unsigned` | 286.480 | **203.890** | 335.303 | 336.103 |
| `dumps_mixed_integers` | 312.286 | **256.525** | 358.297 | 358.537 |
| `dumps_tiny_integers` | 0.140 | 0.148 | 0.115 | **0.115** |
| `dumps_scalar_integer` | **0.076** | 0.077 | 0.089 | 0.089 |
| `dumps_floats` | 321.419 | 318.286 | 297.997 | **297.123** |
| `dumps_float_bits` | 398.895 | 394.665 | 308.745 | **307.807** |

## Strings

Complete-call latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads/short_plain/bytes` | **0.085** | 0.093 | 0.138 | 0.138 |
| `loads/short_plain/bytearray` | **0.106** | 0.109 | 0.147 | 0.149 |
| `loads/short_plain/memoryview` | 0.156 | 0.162 | **0.139** | 0.139 |
| `loads/short_plain/array_view` | 0.155 | 0.163 | **0.138** | 0.138 |
| `dumps/short_plain/object` | 0.083 | **0.075** | 0.086 | 0.086 |
| `loads/short_escaped/bytes` | 0.135 | 0.133 | **0.132** | 0.133 |
| `loads/short_escaped/bytearray` | 0.145 | 0.148 | **0.144** | 0.145 |
| `loads/short_escaped/memoryview` | 0.219 | 0.215 | 0.136 | **0.136** |
| `loads/short_escaped/array_view` | 0.218 | 0.217 | **0.136** | 0.136 |
| `dumps/short_escaped/object` | 0.099 | **0.086** | 0.090 | 0.090 |
| `loads/plain_values/bytes` | 47.918 | 38.632 | 36.693 | **36.503** |
| `loads/plain_values/bytearray` | 48.955 | 39.244 | **36.623** | 36.876 |
| `loads/plain_values/memoryview` | 48.894 | 39.542 | 36.617 | **36.495** |
| `loads/plain_values/array_view` | 49.051 | 39.677 | 36.632 | **36.390** |
| `dumps/plain_values/object` | 24.260 | 21.437 | 12.688 | **12.669** |
| `loads/escaped_values/bytes` | 70.941 | 65.946 | **37.559** | 37.978 |
| `loads/escaped_values/bytearray` | 71.252 | 66.633 | **37.748** | 37.882 |
| `loads/escaped_values/memoryview` | 71.763 | 67.637 | **37.675** | 37.889 |
| `loads/escaped_values/array_view` | 71.672 | 66.856 | **37.804** | 37.844 |
| `dumps/escaped_values/object` | 33.239 | 31.285 | **22.572** | 23.355 |
| `loads/unicode_escapes/bytes` | 158.352 | 141.612 | **52.146** | 52.297 |
| `loads/unicode_escapes/bytearray` | 158.315 | 143.704 | 52.240 | **51.704** |
| `loads/unicode_escapes/memoryview` | 156.858 | 146.417 | 52.131 | **52.074** |
| `loads/unicode_escapes/array_view` | 155.730 | 144.093 | 52.179 | **51.847** |
| `dumps/unicode_escapes/object` | 22.194 | 21.821 | 11.284 | **11.167** |
| `loads/escaped_keys/bytes` | 338.665 | 313.586 | 170.999 | **170.038** |
| `loads/escaped_keys/bytearray` | 339.513 | 316.478 | **171.525** | 175.475 |
| `loads/escaped_keys/memoryview` | 340.466 | 315.625 | 171.127 | **171.052** |
| `loads/escaped_keys/array_view` | 338.359 | 314.008 | 171.418 | **170.862** |
| `dumps/escaped_keys/object` | 105.810 | 91.431 | 46.485 | **45.958** |
| `loads/unique_keys/bytes` | 160.657 | 158.808 | 47.820 | **47.731** |
| `loads/unique_keys/bytearray` | 162.074 | 160.548 | **47.609** | 47.779 |
| `loads/unique_keys/memoryview` | 162.470 | 160.649 | **48.191** | 48.220 |
| `loads/unique_keys/array_view` | 162.882 | 160.285 | **47.916** | 48.106 |
| `dumps/unique_keys/object` | 34.676 | 29.101 | 12.033 | **11.884** |
| `loads/long_plain/bytes` | 22.329 | **17.090** | 96.264 | 94.827 |
| `loads/long_plain/bytearray` | 26.589 | **21.385** | 96.373 | 95.170 |
| `loads/long_plain/memoryview` | 26.619 | **21.405** | 95.600 | 95.287 |
| `loads/long_plain/array_view` | 26.726 | **21.592** | 96.728 | 95.003 |
| `dumps/long_plain/object` | 12.439 | 12.428 | **10.444** | 10.487 |
| `loads/long_escaped/bytes` | 60.955 | **58.624** | 100.142 | 100.209 |
| `loads/long_escaped/bytearray` | 64.618 | **62.015** | 100.497 | 100.502 |
| `loads/long_escaped/memoryview` | 64.718 | **62.999** | 100.141 | 99.641 |
| `loads/long_escaped/array_view` | 64.595 | **62.587** | 100.678 | 100.311 |
| `dumps/long_escaped/object` | 72.793 | **47.889** | 50.885 | 50.573 |
| `loads/late_escape/bytes` | 28.303 | **21.518** | 96.263 | 94.821 |
| `loads/late_escape/bytearray` | 79.038 | **71.612** | 96.036 | 94.895 |
| `loads/late_escape/memoryview` | 79.160 | **71.682** | 95.833 | 95.151 |
| `loads/late_escape/array_view` | 79.583 | **72.340** | 96.110 | 95.336 |
| `dumps/late_escape/object` | 15.562 | 15.758 | **10.226** | 10.251 |
| `loads/medium/bytes` | 386.375 | 367.474 | **249.761** | 251.817 |
| `loads/medium/bytearray` | 379.467 | 364.816 | **249.400** | 250.104 |
| `loads/medium/memoryview` | 381.833 | 365.080 | **249.107** | 249.972 |
| `loads/medium/array_view` | 378.573 | 363.948 | **249.129** | 249.625 |
| `dumps/medium/object` | 162.529 | 146.650 | **90.030** | 90.061 |
| `loads/integers/bytes` | 283.973 | 253.511 | **188.440** | 188.956 |
| `loads/integers/bytearray` | 286.283 | 258.215 | 188.509 | **187.954** |
| `loads/integers/memoryview` | 285.261 | 254.817 | **187.851** | 188.488 |
| `loads/integers/array_view` | 286.043 | 256.947 | 188.356 | **188.209** |
| `dumps/integers/object` | 113.823 | 108.020 | **44.034** | 44.264 |
