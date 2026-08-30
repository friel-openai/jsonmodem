# Maintained suite: original control

Original is the existing PR #3 build (`b7fe329`).
Final is the changed implementation (`b0f3190`).
The reference is orjson 3.11.9. See [definitions and methods](README.md).

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

## Output

Complete-call latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `small` | 0.399 | 0.421 | **0.263** | 0.268 |
| `medium` | 164.598 | 161.698 | **89.598** | 89.707 |
| `integers` | 113.444 | 114.252 | **43.610** | 43.827 |
| `floats` | 318.125 | 317.099 | **292.378** | 292.688 |
| `strings` | 24.632 | 25.052 | **13.091** | 13.093 |
| `escaped` | 91.478 | 91.912 | 41.267 | **40.901** |
| `long_string` | 12.156 | 12.233 | **10.266** | 10.283 |
| `integers_wide_signed` | 261.458 | **259.919** | 353.147 | 352.244 |
| `integers_wide_unsigned` | 279.920 | **278.865** | 331.590 | 330.797 |
| `scalar_integer` | **0.158** | 0.168 | 0.163 | 0.163 |
| `integers_tiny` | 0.230 | 0.239 | **0.196** | 0.196 |
| `indent_integers` | 142.119 | 142.580 | **82.943** | 83.500 |
| `strict_integers` | 114.239 | 114.604 | **43.632** | 43.767 |
| `sorted_medium` | 258.454 | 255.688 | 130.193 | **129.818** |
| `integer_keys` | 37.106 | 35.858 | 35.191 | **34.926** |
| `dataclasses` | 204.957 | 215.555 | **78.675** | 79.400 |
| `dataclass_single` | 0.955 | 0.947 | 0.262 | **0.260** |
| `dataclass_slots_single` | 1.534 | 1.533 | **0.628** | 0.631 |
| `dataclass_slots` | 730.790 | 748.243 | 406.865 | **401.979** |
| `dataclass_nested` | 566.512 | 541.887 | 195.076 | **194.632** |
| `dataclass_indent` | 222.715 | 228.769 | 105.730 | **105.102** |
| `dataclass_sorted` | 615.182 | 585.229 | **215.761** | 215.777 |
| `dataclass_default` | 288.544 | 294.183 | **127.411** | 127.667 |
| `numpy_int64` | **918.590** | 922.554 | 1,330.768 | 1,333.263 |
| `numpy_float32` | **2,795.777** | 2,807.155 | 3,240.747 | 3,254.225 |
| `late_default` | 9.972 | 9.694 | 2.944 | **2.867** |
| `dataclass_fields8` | 404.490 | 421.897 | **171.923** | 171.937 |
| `dataclass_fields16` | 718.116 | 736.084 | 304.041 | **303.389** |

## Frontend

Complete-call latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads_small` | 0.595 | 0.630 | 0.531 | **0.524** |
| `loads_small_bytearray` | 0.626 | 0.630 | 0.529 | **0.526** |
| `loads_small_memoryview` | 0.701 | 0.697 | **0.530** | 0.540 |
| `loads_small_array_view` | 0.690 | 0.685 | **0.529** | 0.531 |
| `loads_medium` | 385.738 | 378.162 | **244.558** | 244.914 |
| `loads_medium_bytearray` | 386.219 | 375.699 | **243.760** | 244.593 |
| `loads_medium_memoryview` | 383.071 | 376.991 | 246.011 | **245.395** |
| `loads_medium_array_view` | 383.599 | 379.676 | **244.940** | 246.574 |
| `loads_integers` | 280.093 | 282.829 | **187.671** | 188.456 |
| `loads_integers_bytearray` | 281.762 | 285.075 | 188.207 | **188.031** |
| `loads_integers_memoryview` | 282.945 | 283.735 | 188.339 | **187.265** |
| `loads_integers_array_view` | 282.141 | 286.216 | 188.274 | **187.679** |
| `loads_floats` | 485.540 | 490.268 | 278.968 | **277.910** |
| `loads_floats_bytearray` | 493.006 | 501.752 | 278.576 | **276.869** |
| `loads_floats_memoryview` | 492.248 | 497.561 | 279.058 | **279.032** |
| `loads_floats_array_view` | 490.340 | 498.040 | 279.073 | **277.099** |
| `loads_strings` | 47.690 | 48.055 | **36.589** | 36.629 |
| `loads_strings_bytearray` | 48.618 | 48.970 | **36.690** | 36.878 |
| `loads_strings_memoryview` | 48.833 | 49.267 | 36.685 | **36.603** |
| `loads_strings_array_view` | 48.460 | 48.976 | **36.639** | 36.849 |
| `loads_escaped` | 244.606 | 248.057 | 143.255 | **143.120** |
| `loads_escaped_bytearray` | 246.179 | 251.998 | **143.349** | 144.038 |
| `loads_escaped_memoryview` | 245.670 | 250.582 | 144.350 | **144.081** |
| `loads_escaped_array_view` | 245.072 | 250.269 | **143.085** | 143.788 |
| `loads_long_string` | **19.193** | 21.697 | 93.657 | 93.195 |
| `loads_long_string_bytearray` | **24.722** | 26.142 | 94.008 | 93.038 |
| `loads_long_string_memoryview` | **24.252** | 26.407 | 93.828 | 93.064 |
| `loads_long_string_array_view` | **24.509** | 26.128 | 93.504 | 92.967 |
| `dumps_root_empty` | 0.152 | **0.145** | 0.167 | 0.167 |
| `loads_root_empty` | 0.132 | 0.147 | 0.093 | **0.092** |
| `dumps_root_tiny` | **0.160** | 0.168 | 0.166 | 0.167 |
| `loads_root_tiny` | **0.165** | 0.171 | 0.197 | 0.196 |
| `dumps_root_below_threshold` | 0.261 | 0.282 | 0.219 | **0.219** |
| `loads_root_below_threshold` | **0.211** | 0.233 | 0.274 | 0.273 |
| `dumps_root_at_threshold` | **0.162** | 0.173 | 0.221 | 0.221 |
| `loads_root_at_threshold` | **0.208** | 0.244 | 0.276 | 0.273 |
| `dumps_root_medium` | 0.530 | 0.548 | 0.519 | **0.519** |
| `loads_root_medium` | **0.779** | 0.853 | 1.463 | 1.461 |
| `dumps_root_long` | 11.039 | 11.098 | **9.220** | 9.246 |
| `loads_root_long` | **17.743** | 19.811 | 85.159 | 84.116 |
| `dumps_root_early_quote` | 13.489 | 13.687 | 9.217 | **9.210** |
| `loads_root_early_quote` | **23.380** | 25.387 | 90.084 | 89.607 |
| `dumps_root_late_quote` | 13.685 | 13.735 | 9.249 | **9.190** |
| `loads_root_late_quote` | **23.410** | 25.408 | 85.519 | 84.917 |
| `dumps_root_dense_escapes` | 228.693 | 228.084 | 189.246 | **189.201** |
| `loads_root_dense_escapes` | 266.844 | **117.432** | 128.206 | 127.445 |
| `dumps_root_latin1` | 11.466 | 11.419 | **8.545** | 8.561 |
| `loads_root_latin1` | 98.587 | 98.466 | 94.159 | **93.546** |
| `dumps_root_bmp` | 11.468 | 11.634 | **8.562** | 8.611 |
| `loads_root_bmp` | 97.816 | 97.896 | 83.026 | **82.286** |
| `dumps_root_non_bmp` | 11.797 | 11.956 | **8.551** | 8.637 |
| `loads_root_non_bmp` | 86.720 | 86.753 | 66.876 | **66.163** |
| `dumps_root_append_newline` | 11.183 | 11.250 | **9.297** | 9.343 |
| `dumps_root_indent` | 11.177 | 11.283 | **9.317** | 9.348 |
| `loads_escaped_values` | 65.052 | 64.492 | 34.399 | **34.386** |
| `loads_unicode_escapes` | 150.775 | 142.646 | 45.881 | **45.827** |
| `loads_repeated_escaped_keys` | 138.097 | 124.644 | **87.899** | 88.063 |
| `loads_unique_escaped_keys` | 148.920 | 145.669 | 37.677 | **36.653** |

## Numbers

Complete-call latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads_small` | 0.344 | 0.326 | 0.272 | **0.270** |
| `loads_medium` | 324.040 | 309.279 | 194.600 | **194.109** |
| `loads_integers` | 279.642 | 285.317 | **186.783** | 187.958 |
| `loads_random_small` | 339.373 | 342.074 | 242.060 | **240.141** |
| `loads_wide_signed` | 462.700 | 466.839 | **343.271** | 355.670 |
| `loads_wide_unsigned` | 401.280 | 411.064 | **269.594** | 272.863 |
| `loads_mixed_integers` | 473.490 | 483.909 | **344.029** | 351.286 |
| `loads_tiny_integers` | 0.219 | 0.209 | 0.202 | **0.201** |
| `loads_scalar_integer` | 0.085 | **0.081** | 0.116 | 0.117 |
| `loads_floats` | 485.213 | 493.725 | **276.981** | 277.451 |
| `loads_float_bits` | 726.351 | 733.980 | **429.124** | 430.278 |
| `loads_overflow_integers` | 944.071 | 996.018 | 661.286 | **659.951** |
| `loads_long_fractions` | 749.173 | 754.406 | **439.645** | 440.384 |
| `loads_zero_forms` | 0.347 | 0.341 | **0.229** | 0.231 |
| `dumps_small` | 0.201 | 0.201 | **0.128** | 0.131 |
| `dumps_medium` | 146.727 | 141.952 | **79.309** | 79.503 |
| `dumps_integers` | 112.601 | 112.825 | 43.092 | **42.984** |
| `dumps_random_small` | 152.257 | 150.209 | **74.520** | 74.790 |
| `dumps_wide_signed` | **264.266** | 265.604 | 357.303 | 358.432 |
| `dumps_wide_unsigned` | **283.718** | 284.217 | 335.893 | 335.784 |
| `dumps_mixed_integers` | 306.480 | **306.257** | 358.432 | 357.848 |
| `dumps_tiny_integers` | 0.142 | 0.144 | **0.115** | 0.115 |
| `dumps_scalar_integer` | **0.076** | 0.076 | 0.089 | 0.090 |
| `dumps_floats` | 323.097 | 321.101 | 303.092 | **298.605** |
| `dumps_float_bits` | 394.124 | 396.953 | 308.990 | **307.900** |

## Strings

Complete-call latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `loads/short_plain/bytes` | 0.094 | **0.084** | 0.138 | 0.135 |
| `loads/short_plain/bytearray` | 0.106 | **0.103** | 0.147 | 0.144 |
| `loads/short_plain/memoryview` | 0.141 | 0.154 | **0.137** | 0.138 |
| `loads/short_plain/array_view` | 0.142 | 0.155 | 0.138 | **0.136** |
| `dumps/short_plain/object` | **0.078** | 0.083 | 0.086 | 0.086 |
| `loads/short_escaped/bytes` | 0.137 | 0.134 | **0.131** | 0.132 |
| `loads/short_escaped/bytearray` | 0.157 | 0.145 | **0.144** | 0.144 |
| `loads/short_escaped/memoryview` | 0.220 | 0.218 | 0.135 | **0.135** |
| `loads/short_escaped/array_view` | 0.220 | 0.218 | **0.135** | 0.135 |
| `dumps/short_escaped/object` | **0.086** | 0.099 | 0.089 | 0.090 |
| `loads/plain_values/bytes` | 47.168 | 47.780 | 36.479 | **36.374** |
| `loads/plain_values/bytearray` | 48.626 | 48.811 | 36.568 | **36.501** |
| `loads/plain_values/memoryview` | 48.415 | 48.540 | **36.560** | 36.566 |
| `loads/plain_values/array_view` | 48.384 | 48.855 | 36.740 | **36.606** |
| `dumps/plain_values/object` | 24.207 | 24.297 | **12.682** | 12.737 |
| `loads/escaped_values/bytes` | 70.269 | 70.978 | 37.787 | **37.622** |
| `loads/escaped_values/bytearray` | 70.882 | 71.547 | 37.856 | **37.651** |
| `loads/escaped_values/memoryview` | 70.848 | 71.622 | **37.697** | 37.699 |
| `loads/escaped_values/array_view` | 71.064 | 71.659 | **38.000** | 38.284 |
| `dumps/escaped_values/object` | 33.470 | 33.217 | **22.344** | 23.023 |
| `loads/unicode_escapes/bytes` | 154.790 | 155.578 | 52.053 | **51.862** |
| `loads/unicode_escapes/bytearray` | 155.803 | 155.123 | 52.041 | **51.582** |
| `loads/unicode_escapes/memoryview` | 157.496 | 155.160 | 52.059 | **51.950** |
| `loads/unicode_escapes/array_view` | 157.619 | 156.398 | 52.094 | **52.001** |
| `dumps/unicode_escapes/object` | 22.377 | 22.173 | **11.144** | 11.189 |
| `loads/escaped_keys/bytes` | 331.923 | 338.663 | 170.732 | **170.640** |
| `loads/escaped_keys/bytearray` | 334.170 | 339.738 | 171.343 | **171.014** |
| `loads/escaped_keys/memoryview` | 333.656 | 337.693 | 171.874 | **170.330** |
| `loads/escaped_keys/array_view` | 332.007 | 337.976 | 172.002 | **171.659** |
| `dumps/escaped_keys/object` | 105.553 | 103.821 | **45.910** | 46.994 |
| `loads/unique_keys/bytes` | 162.857 | 160.715 | 47.781 | **47.447** |
| `loads/unique_keys/bytearray` | 162.848 | 160.780 | 47.927 | **47.526** |
| `loads/unique_keys/memoryview` | 163.294 | 162.221 | **47.678** | 47.725 |
| `loads/unique_keys/array_view` | 164.233 | 162.352 | **47.791** | 47.922 |
| `dumps/unique_keys/object` | 34.941 | 34.628 | **11.916** | 11.943 |
| `loads/long_plain/bytes` | **19.554** | 22.123 | 95.692 | 94.933 |
| `loads/long_plain/bytearray` | **23.914** | 26.301 | 95.839 | 95.257 |
| `loads/long_plain/memoryview` | **23.930** | 26.403 | 95.417 | 94.949 |
| `loads/long_plain/array_view` | **24.104** | 26.949 | 95.957 | 95.175 |
| `dumps/long_plain/object` | 12.451 | 12.466 | **10.407** | 10.549 |
| `loads/long_escaped/bytes` | 93.437 | **60.787** | 99.913 | 100.174 |
| `loads/long_escaped/bytearray` | 96.884 | **64.474** | 99.986 | 100.217 |
| `loads/long_escaped/memoryview` | 97.352 | **64.672** | 100.142 | 100.510 |
| `loads/long_escaped/array_view` | 97.154 | **64.908** | 100.232 | 100.377 |
| `dumps/long_escaped/object` | 70.927 | 72.207 | **50.620** | 52.992 |
| `loads/late_escape/bytes` | **25.607** | 28.249 | 96.416 | 95.166 |
| `loads/late_escape/bytearray` | **75.315** | 78.436 | 95.881 | 95.065 |
| `loads/late_escape/memoryview` | **75.661** | 78.725 | 95.916 | 94.992 |
| `loads/late_escape/array_view` | **76.156** | 79.126 | 95.939 | 95.286 |
| `dumps/late_escape/object` | 15.151 | 15.248 | **10.235** | 10.279 |
| `loads/medium/bytes` | 385.617 | 378.514 | **249.610** | 250.476 |
| `loads/medium/bytearray` | 395.921 | 392.738 | **249.099** | 251.379 |
| `loads/medium/memoryview` | 399.363 | 383.847 | **249.119** | 249.434 |
| `loads/medium/array_view` | 397.790 | 382.516 | **250.413** | 250.865 |
| `dumps/medium/object` | 164.405 | 161.554 | **90.281** | 90.382 |
| `loads/integers/bytes` | 281.280 | 283.318 | 189.496 | **187.605** |
| `loads/integers/bytearray` | 282.485 | 286.406 | 189.730 | **188.554** |
| `loads/integers/memoryview` | 281.607 | 285.580 | **187.596** | 188.008 |
| `loads/integers/array_view` | 282.697 | 287.172 | 190.103 | **188.792** |
| `dumps/integers/object` | 113.645 | 114.827 | **44.014** | 44.286 |
