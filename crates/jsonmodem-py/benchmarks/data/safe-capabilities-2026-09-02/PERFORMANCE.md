# Complete-call benchmark results

These results measure complete loads() and dumps() calls. Bold marks every exact row minimum, including ties.

PR #6 is the previous jsonmodem build. Rebuilt uses the same runtime source
compiled again. Earlier is an intermediate build; Selected is the build in
this PR. Their runtime revisions and binary hashes are in results.json.
A later publication revision is recorded separately from the measured revision.

Each suite and jsonmodem build ran in five fresh Python processes. Each process recorded three samples for jsonmodem and orjson. Each jsonmodem cell uses the median of five process medians. The displayed orjson cell uses all twenty reference process medians, five per jsonmodem build. All raw samples and paired comparisons remain in results.json.

The geometric means weight each comparable case equally. They summarize case latencies, not elapsed time to execute a suite. The three unequal-output date cases are excluded from all means, win counts and regression comparisons, matching the validated comparison.

## Overall and suite means

Microseconds per complete call; **lower is better**.

| Geometric mean | PR #6 | Rebuilt | Earlier | Selected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall (275 comparable cases) | 44.793 | 44.642 | 43.879 | 41.840 | **35.099** |
| Encoding (28 cases) | 65.563 | 64.496 | 63.265 | 62.498 | **38.734** |
| Complete-call inputs (58 cases) | 19.452 | 19.524 | 19.097 | **18.900** | 19.286 |
| Numbers (25 cases) | 38.624 | 38.735 | 38.358 | 38.633 | **30.824** |
| Strings (60 cases) | 28.639 | 28.690 | 27.507 | 26.949 | **23.371** |
| Dates (40 cases) | 18.665 | 18.359 | 19.057 | 16.167 | **11.865** |
| NumPy dates (28 cases) | 21.125 | 21.002 | 21.001 | **17.523** | 23.009 |
| Public documents (36 cases) | 1,415.423 | 1,413.933 | 1,350.995 | 1,372.104 | **852.163** |

## Encoding

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Rebuilt | Earlier | Selected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| small | 0.373 | 0.376 | 0.370 | 0.366 | **0.258** |
| medium | 145.480 | 146.205 | 149.530 | 151.991 | **90.097** |
| integers | 108.030 | 108.039 | 108.097 | 107.775 | **44.769** |
| floats | 313.088 | 312.929 | 318.511 | 318.134 | **294.315** |
| strings | 22.578 | 22.700 | 22.067 | 23.395 | **14.173** |
| escaped | 89.379 | 89.582 | 92.052 | 93.988 | **41.602** |
| long_string | 12.325 | 12.117 | 12.135 | 12.393 | **10.272** |
| integers_wide_signed | 249.956 | 251.170 | 244.692 | **239.603** | 353.644 |
| integers_wide_unsigned | 203.099 | 199.184 | **196.398** | 204.633 | 332.147 |
| scalar_integer | 0.172 | 0.168 | 0.159 | **0.156** | 0.164 |
| integers_tiny | 0.253 | 0.249 | 0.239 | 0.223 | **0.201** |
| indent_integers | 135.154 | 136.236 | 130.841 | 133.425 | **83.803** |
| strict_integers | 114.935 | 114.287 | 113.925 | 114.298 | **45.025** |
| sorted_medium | 298.134 | 295.899 | 303.421 | 309.220 | **132.888** |
| integer_keys | 36.092 | 36.523 | 39.045 | 38.738 | **35.144** |
| dataclasses | 201.051 | 194.140 | 189.496 | 177.333 | **78.225** |
| dataclass_single | 0.942 | 0.957 | 0.947 | 0.955 | **0.266** |
| dataclass_slots_single | 1.532 | 1.564 | 1.495 | 1.522 | **0.628** |
| dataclass_slots | 754.334 | 736.614 | 714.820 | 728.986 | **394.779** |
| dataclass_nested | 577.825 | 516.518 | 503.796 | 468.888 | **194.163** |
| dataclass_indent | 213.697 | 207.323 | 205.861 | 193.614 | **105.888** |
| dataclass_sorted | 630.770 | 565.272 | 548.673 | 516.309 | **217.741** |
| dataclass_default | 267.119 | 262.788 | 259.004 | 252.048 | **128.937** |
| numpy_int64 | 958.009 | 938.321 | 921.388 | **921.358** | 1,341.074 |
| numpy_float32 | 2,887.520 | 2,820.197 | **2,797.111** | 2,802.380 | 3,283.175 |
| late_default | 9.914 | 10.009 | 9.226 | 8.864 | **3.295** |
| dataclass_fields8 | 439.179 | 417.559 | 388.434 | 353.620 | **174.863** |
| dataclass_fields16 | 798.631 | 766.004 | 685.845 | 663.441 | **305.737** |

## Complete-call inputs

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Rebuilt | Earlier | Selected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| loads_small | 0.564 | 0.568 | 0.558 | 0.623 | **0.522** |
| loads_small_bytearray | 0.5834 | 0.5922 | 0.5918 | 0.6578 | **0.5231** |
| loads_small_memoryview | 0.667 | 0.660 | 0.659 | 0.726 | **0.524** |
| loads_small_array_view | 0.675 | 0.671 | 0.663 | 0.730 | **0.526** |
| loads_medium | 357.531 | 364.039 | 305.040 | 327.861 | **243.666** |
| loads_medium_bytearray | 365.614 | 359.492 | 312.856 | 333.977 | **244.034** |
| loads_medium_memoryview | 362.956 | 362.266 | 307.310 | 325.521 | **244.888** |
| loads_medium_array_view | 364.379 | 372.564 | 311.618 | 330.261 | **245.375** |
| loads_integers | 255.211 | 257.220 | 258.224 | 256.317 | **189.459** |
| loads_integers_bytearray | 260.893 | 256.257 | 261.621 | 257.870 | **189.841** |
| loads_integers_memoryview | 257.912 | 262.543 | 261.175 | 258.768 | **189.381** |
| loads_integers_array_view | 258.788 | 259.279 | 261.918 | 259.276 | **188.788** |
| loads_floats | 460.756 | 462.660 | 464.222 | 455.471 | **280.040** |
| loads_floats_bytearray | 470.546 | 469.799 | 471.342 | 462.756 | **279.342** |
| loads_floats_memoryview | 471.944 | 470.082 | 471.429 | 462.706 | **279.847** |
| loads_floats_array_view | 468.513 | 470.294 | 471.530 | 466.345 | **280.621** |
| loads_strings | 39.117 | 39.292 | 39.344 | 38.277 | **36.814** |
| loads_strings_bytearray | 39.848 | 40.270 | 40.531 | 39.310 | **36.926** |
| loads_strings_memoryview | 40.113 | 40.628 | 40.567 | 39.514 | **36.732** |
| loads_strings_array_view | 40.455 | 40.676 | 40.358 | 39.456 | **36.798** |
| loads_escaped | 247.234 | 250.809 | 233.385 | 237.759 | **144.762** |
| loads_escaped_bytearray | 251.685 | 248.982 | 234.971 | 238.021 | **143.375** |
| loads_escaped_memoryview | 250.679 | 248.272 | 236.908 | 239.087 | **143.382** |
| loads_escaped_array_view | 250.504 | 260.407 | 234.489 | 239.160 | **144.496** |
| loads_long_string | 16.806 | 17.019 | 16.782 | **14.393** | 92.821 |
| loads_long_string_bytearray | 21.122 | 21.290 | 21.891 | **18.743** | 93.393 |
| loads_long_string_memoryview | 21.068 | 21.569 | 21.591 | **18.517** | 93.015 |
| loads_long_string_array_view | 21.041 | 21.118 | 21.431 | **18.548** | 93.152 |
| dumps_root_empty | **0.139** | 0.143 | 0.150 | 0.141 | 0.156 |
| loads_root_empty | 0.137 | 0.138 | 0.135 | 0.146 | **0.093** |
| dumps_root_tiny | 0.1537 | 0.1538 | 0.1600 | **0.1471** | 0.1572 |
| loads_root_tiny | 0.15845 | 0.15794 | **0.15790** | 0.16687 | 0.20596 |
| dumps_root_below_threshold | 0.2622 | 0.2644 | 0.2710 | **0.2608** | 0.2618 |
| loads_root_below_threshold | 0.1929 | **0.1926** | 0.1950 | 0.2064 | 0.2716 |
| dumps_root_at_threshold | 0.147 | **0.146** | 0.156 | 0.155 | 0.256 |
| loads_root_at_threshold | 0.1981 | **0.1957** | 0.1980 | 0.2058 | 0.2721 |
| dumps_root_medium | 0.539 | 0.521 | 0.543 | **0.510** | 0.518 |
| loads_root_medium | 0.681 | 0.670 | 0.689 | **0.621** | 1.476 |
| dumps_root_long | 11.0809 | 10.9753 | 11.0921 | 11.0811 | **9.0243** |
| loads_root_long | 15.241 | 15.364 | 15.346 | **13.098** | 85.006 |
| dumps_root_early_quote | 13.611 | 13.803 | 15.308 | 14.094 | **9.071** |
| loads_root_early_quote | 19.341 | 19.430 | 18.851 | **17.819** | 90.203 |
| dumps_root_late_quote | 13.356 | 13.578 | 15.221 | 14.405 | **9.168** |
| loads_root_late_quote | 19.395 | 19.472 | 18.877 | **17.306** | 85.460 |
| dumps_root_dense_escapes | 87.509 | 87.916 | **79.281** | 83.144 | 188.510 |
| loads_root_dense_escapes | 123.099 | 120.509 | 120.682 | 119.291 | **117.183** |
| dumps_root_latin1 | 11.728 | 11.405 | 11.743 | 11.778 | **8.616** |
| loads_root_latin1 | 99.721 | 98.412 | 98.772 | 101.060 | **94.422** |
| dumps_root_bmp | 11.297 | 11.910 | 11.542 | 11.526 | **8.684** |
| loads_root_bmp | 97.947 | 97.563 | 97.809 | 99.024 | **82.738** |
| dumps_root_non_bmp | 11.569 | 12.245 | 12.246 | 11.605 | **8.613** |
| loads_root_non_bmp | 86.843 | 86.763 | 86.727 | 87.603 | **66.697** |
| dumps_root_append_newline | 11.293 | 11.144 | 11.204 | 11.171 | **9.148** |
| dumps_root_indent | 11.184 | 11.175 | 11.284 | 11.187 | **9.209** |
| loads_escaped_values | 54.686 | 55.211 | 56.035 | 54.561 | **34.455** |
| loads_unicode_escapes | 137.764 | 138.111 | 136.538 | 135.360 | **46.034** |
| loads_repeated_escaped_keys | 122.091 | 123.133 | 111.644 | 119.894 | **87.469** |
| loads_unique_escaped_keys | 143.357 | 143.018 | 78.044 | 78.748 | **36.786** |

## Numbers

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Rebuilt | Earlier | Selected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| loads_small | 0.313 | 0.307 | 0.308 | 0.327 | **0.260** |
| loads_medium | 294.353 | 294.710 | 252.595 | 271.040 | **194.816** |
| loads_integers | 255.983 | 258.133 | 262.617 | 258.528 | **187.158** |
| loads_random_small | 313.774 | 315.874 | 322.672 | 314.996 | **241.950** |
| loads_wide_signed | 438.628 | 442.707 | 446.572 | 432.901 | **351.925** |
| loads_wide_unsigned | 383.649 | 393.087 | 390.731 | 379.440 | **271.693** |
| loads_mixed_integers | 446.386 | 446.688 | 453.576 | 446.700 | **350.328** |
| loads_tiny_integers | 0.2001 | **0.1978** | 0.2035 | 0.2147 | 0.1981 |
| loads_scalar_integer | 0.083 | 0.084 | 0.081 | **0.077** | 0.116 |
| loads_floats | 465.142 | 468.273 | 469.859 | 455.187 | **277.772** |
| loads_float_bits | 722.717 | 703.488 | 699.985 | 696.293 | **429.130** |
| loads_overflow_integers | 923.009 | 914.052 | 918.974 | 918.803 | **663.743** |
| loads_long_fractions | 726.167 | 732.158 | 728.585 | 740.595 | **439.706** |
| loads_zero_forms | 0.316 | 0.320 | 0.337 | 0.352 | **0.225** |
| dumps_small | 0.1689 | 0.1695 | 0.1717 | 0.1728 | **0.1222** |
| dumps_medium | 126.682 | 126.805 | 128.614 | 129.086 | **79.630** |
| dumps_integers | 108.602 | 110.062 | 106.878 | 106.473 | **44.625** |
| dumps_random_small | 161.349 | 161.596 | 153.350 | 155.545 | **76.522** |
| dumps_wide_signed | 251.281 | 257.040 | 248.018 | **246.648** | 359.542 |
| dumps_wide_unsigned | **203.004** | 206.679 | 203.267 | 209.290 | 337.690 |
| dumps_mixed_integers | 255.179 | 260.226 | 257.123 | **254.656** | 360.708 |
| dumps_tiny_integers | 0.1474 | 0.1472 | 0.1378 | 0.1391 | **0.1098** |
| dumps_scalar_integer | 0.07646 | 0.07655 | **0.07628** | 0.08223 | 0.08117 |
| dumps_floats | 323.253 | 319.609 | 322.437 | 325.906 | **299.883** |
| dumps_float_bits | 400.564 | 397.409 | 390.583 | 393.503 | **310.385** |

## Strings

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Rebuilt | Earlier | Selected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| loads/short_plain/bytes | 0.0917 | 0.0922 | 0.0827 | **0.0820** | 0.1217 |
| loads/short_plain/bytearray | 0.108 | 0.109 | 0.097 | **0.095** | 0.125 |
| loads/short_plain/memoryview | 0.163 | 0.172 | 0.160 | 0.162 | **0.125** |
| loads/short_plain/array_view | 0.163 | 0.171 | 0.160 | 0.162 | **0.125** |
| dumps/short_plain/object | 0.07640 | **0.07519** | 0.07638 | 0.08126 | 0.07990 |
| loads/short_escaped/bytes | 0.133 | 0.132 | 0.128 | **0.123** | 0.129 |
| loads/short_escaped/bytearray | 0.146 | 0.144 | 0.142 | 0.136 | **0.133** |
| loads/short_escaped/memoryview | 0.216 | 0.219 | 0.212 | 0.209 | **0.132** |
| loads/short_escaped/array_view | 0.2144 | 0.2225 | 0.2142 | 0.2114 | **0.1318** |
| dumps/short_escaped/object | 0.0851 | 0.0850 | 0.0863 | 0.0911 | **0.0837** |
| loads/plain_values/bytes | 38.884 | 39.285 | 39.767 | 39.076 | **36.540** |
| loads/plain_values/bytearray | 40.428 | 40.376 | 41.076 | 39.858 | **36.568** |
| loads/plain_values/memoryview | 39.644 | 40.233 | 40.967 | 40.378 | **36.426** |
| loads/plain_values/array_view | 40.106 | 40.151 | 41.060 | 39.731 | **36.546** |
| dumps/plain_values/object | 23.061 | 22.991 | 21.503 | 23.446 | **14.176** |
| loads/escaped_values/bytes | 65.598 | 65.949 | 67.120 | 65.911 | **37.939** |
| loads/escaped_values/bytearray | 66.336 | 66.567 | 67.435 | 66.668 | **37.792** |
| loads/escaped_values/memoryview | 66.878 | 66.545 | 68.248 | 66.598 | **37.778** |
| loads/escaped_values/array_view | 66.517 | 66.365 | 67.689 | 66.884 | **37.938** |
| dumps/escaped_values/object | 31.965 | 31.652 | 32.622 | 33.912 | **23.290** |
| loads/unicode_escapes/bytes | 142.738 | 143.188 | 140.965 | 141.119 | **55.272** |
| loads/unicode_escapes/bytearray | 143.875 | 147.620 | 145.669 | 142.697 | **55.484** |
| loads/unicode_escapes/memoryview | 143.049 | 146.685 | 142.353 | 142.496 | **55.123** |
| loads/unicode_escapes/array_view | 144.103 | 143.560 | 147.556 | 142.563 | **55.501** |
| dumps/unicode_escapes/object | 22.414 | 21.987 | 28.172 | 22.285 | **11.920** |
| loads/escaped_keys/bytes | 318.777 | 313.663 | 300.545 | 308.131 | **170.852** |
| loads/escaped_keys/bytearray | 318.189 | 316.902 | 300.981 | 312.278 | **171.506** |
| loads/escaped_keys/memoryview | 317.792 | 316.212 | 299.898 | 309.612 | **171.457** |
| loads/escaped_keys/array_view | 320.289 | 316.114 | 300.419 | 312.043 | **172.617** |
| dumps/escaped_keys/object | 91.842 | 91.421 | 94.013 | 95.119 | **47.061** |
| loads/unique_keys/bytes | 158.387 | 156.328 | 97.767 | 97.705 | **47.888** |
| loads/unique_keys/bytearray | 158.622 | 158.342 | 98.047 | 97.661 | **47.762** |
| loads/unique_keys/memoryview | 162.165 | 159.075 | 98.404 | 98.587 | **48.542** |
| loads/unique_keys/array_view | 159.959 | 158.168 | 98.048 | 98.510 | **48.040** |
| dumps/unique_keys/object | 28.730 | 28.804 | 27.864 | 29.912 | **12.503** |
| loads/long_plain/bytes | 17.201 | 17.072 | 17.143 | **14.772** | 95.983 |
| loads/long_plain/bytearray | 21.573 | 21.751 | 21.854 | **18.596** | 95.653 |
| loads/long_plain/memoryview | 21.789 | 21.660 | 22.065 | **18.652** | 95.591 |
| loads/long_plain/array_view | 21.715 | 21.567 | 22.238 | **18.910** | 95.697 |
| dumps/long_plain/object | 12.535 | 12.437 | 12.594 | 12.682 | **10.236** |
| loads/long_escaped/bytes | 58.564 | 60.195 | 63.114 | **57.930** | 100.001 |
| loads/long_escaped/bytearray | **61.881** | 64.556 | 65.392 | 62.025 | 99.997 |
| loads/long_escaped/memoryview | 62.424 | 64.892 | 66.622 | **62.319** | 100.045 |
| loads/long_escaped/array_view | **61.849** | 64.277 | 65.837 | 62.093 | 99.942 |
| dumps/long_escaped/object | 48.171 | 48.367 | **47.290** | 47.941 | 51.931 |
| loads/late_escape/bytes | 22.473 | 21.515 | 23.819 | **19.054** | 96.069 |
| loads/late_escape/bytearray | 72.415 | 72.193 | 72.975 | **69.972** | 95.709 |
| loads/late_escape/memoryview | 72.058 | 72.438 | 73.899 | **70.790** | 95.779 |
| loads/late_escape/array_view | 72.708 | 73.175 | 73.778 | **69.667** | 95.583 |
| dumps/late_escape/object | 15.612 | 15.541 | 15.266 | 15.492 | **10.180** |
| loads/medium/bytes | 362.805 | 364.600 | 313.366 | 331.834 | **248.545** |
| loads/medium/bytearray | 378.834 | 367.040 | 314.967 | 335.787 | **248.185** |
| loads/medium/memoryview | 379.278 | 373.021 | 313.776 | 334.625 | **249.263** |
| loads/medium/array_view | 380.624 | 373.564 | 318.263 | 335.756 | **248.861** |
| dumps/medium/object | 145.546 | 147.699 | 149.732 | 150.975 | **91.531** |
| loads/integers/bytes | 258.987 | 257.802 | 260.743 | 252.826 | **188.807** |
| loads/integers/bytearray | 261.875 | 259.541 | 262.986 | 254.952 | **189.908** |
| loads/integers/memoryview | 260.925 | 259.653 | 264.959 | 254.398 | **189.334** |
| loads/integers/array_view | 257.491 | 258.708 | 262.269 | 254.778 | **188.083** |
| dumps/integers/object | 108.392 | 107.792 | 107.491 | 106.216 | **44.617** |

## Dates

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Rebuilt | Earlier | Selected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| datetime_naive_scalar | 0.626 | 0.621 | 0.638 | 0.641 | **0.197** |
| datetime_naive_16 | 1.672 | 1.667 | 1.751 | 1.577 | **0.618** |
| datetime_naive_1024 | 56.396 | 54.582 | 58.134 | 43.259 | **30.135** |
| datetime_utc_scalar | 0.634 | 0.637 | 0.646 | 0.655 | **0.273** |
| datetime_utc_16 | 1.824 | 1.833 | 1.939 | **1.729** | 1.739 |
| datetime_utc_1024 | 66.676 | 61.954 | 69.472 | **50.734** | 101.112 |
| datetime_fixed_offset_scalar | 0.68065 | 0.68066 | 0.69565 | 0.72780 | **0.28518** |
| datetime_fixed_offset_16 | 2.299 | 2.315 | 2.455 | 2.216 | **1.907** |
| datetime_fixed_offset_1024 | 91.765 | 92.665 | 99.908 | **78.840** | 111.531 |
| date_scalar | 0.602 | 0.604 | 0.616 | 0.632 | **0.191** |
| date_16 | 1.303 | 1.305 | 1.310 | 1.203 | **0.450** |
| date_1024 | 40.752 | 40.051 | 40.142 | 29.594 | **18.377** |
| time_scalar | 0.617 | 0.623 | 0.625 | 0.647 | **0.198** |
| datetime_naive_1024_zero_microseconds | 50.163 | 48.558 | 51.398 | 37.396 | **25.327** |
| datetime_utc_1024_zero_microseconds | 58.711 | 55.542 | 61.002 | **43.743** | 93.167 |
| time_1024_zero_microseconds | 50.479 | 50.742 | 49.727 | 39.510 | **20.150** |
| datetime_naive_1024_naive_utc | 59.522 | 57.187 | 61.169 | 46.573 | **32.678** |
| datetime_naive_1024_omit_microseconds | 50.443 | 49.596 | 51.396 | 38.424 | **23.384** |
| datetime_naive_1024_utc_z | 57.145 | 54.439 | 57.948 | 44.677 | **30.198** |
| datetime_naive_1024_naive_utc_omit_microseconds | 51.306 | 49.181 | 52.274 | 38.507 | **25.901** |
| datetime_naive_1024_naive_utc_z | 57.045 | 54.336 | 58.637 | 43.735 | **32.104** |
| datetime_naive_1024_omit_microseconds_utc_z | 50.852 | 49.323 | 51.600 | 37.702 | **23.693** |
| datetime_naive_1024_naive_utc_omit_microseconds_utc_z | 50.973 | 49.892 | 52.261 | 38.124 | **25.339** |
| datetime_utc_1024_omit_microseconds | 58.658 | 58.179 | 60.903 | **44.104** | 92.954 |
| datetime_utc_1024_utc_z | 64.618 | 62.010 | 67.126 | **50.333** | 99.456 |
| datetime_utc_1024_omit_microseconds_utc_z | 58.541 | 54.962 | 60.175 | **43.581** | 92.392 |
| time_1024_omit_microseconds | 50.939 | 49.955 | 49.694 | 39.393 | **19.893** |
| date_1024_options | 40.683 | 40.153 | 40.759 | 29.469 | **18.454** |
| dataclass_dates | 238.519 | 231.396 | 236.370 | 208.835 | **187.920** |
| datetime_passthrough | 926.272 | 906.830 | 909.258 | 930.634 | **661.442** |
| datetime_subclass | 754.320 | 745.863 | 733.393 | 742.550 | **699.376** |
| datetime_named_zero_offset_1024 | 87.690 | 83.662 | 91.701 | **73.965** | 101.906 |
| datetime_negative_offset_1024 | 91.342 | 90.852 | 97.465 | **78.896** | 110.800 |
| datetime_seconds_offset_1024 | 91.981 | 91.085 | 97.701 | **80.707** | 110.683 |
| uuid_scalar_control | 0.645 | 0.642 | 0.672 | 0.677 | **0.226** |
| uuid_list_control | 79.279 | 79.703 | 81.236 | 80.529 | **47.111** |
| dict_control | 0.264 | 0.267 | 0.279 | 0.281 | **0.225** |
| list_control | 10.745 | 10.866 | 9.956 | 11.655 | **4.408** |
| string_control | 0.168 | 0.169 | 0.167 | **0.154** | 0.171 |
| dataclass_control | 202.666 | 203.331 | 199.311 | 181.342 | **83.391** |

## NumPy dates

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Rebuilt | Earlier | Selected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| datetime_Y_scalar | 3.128 | 3.085 | 3.110 | 2.835 | **0.878** |
| datetime_Y_16 | 3.421 | 3.416 | 3.451 | 3.507 | **1.921** |
| datetime_Y_4096 | 72.251 | 72.071 | **70.841** | 75.166 | 266.161 |
| datetime_M_scalar | 3.143 | 3.090 | 3.079 | 2.815 | **0.884** |
| datetime_M_16 | 3.494 | 3.488 | 3.489 | 3.582 | **1.973** |
| datetime_M_4096 | 81.939 | 81.436 | **80.035** | 82.632 | 280.454 |
| datetime_D_scalar | 3.153 | 3.098 | 3.116 | 2.787 | **0.878** |
| datetime_D_16 | 3.556 | 3.539 | 3.570 | 3.605 | **1.911** |
| datetime_D_4096 | 108.048 | 107.208 | 107.216 | **104.898** | 267.506 |
| datetime_s_scalar | 3.119 | 3.081 | 3.100 | 2.802 | **0.876** |
| datetime_s_16 | 3.495 | 3.499 | 3.540 | 3.442 | **1.937** |
| datetime_s_4096 | 102.337 | 101.670 | 102.836 | **69.783** | 275.609 |
| datetime_us_scalar | 3.212 | 3.162 | 3.182 | 2.863 | **0.916** |
| datetime_us_16 | 3.590 | 3.574 | 3.612 | 3.517 | **2.044** |
| datetime_us_4096 | 113.928 | 113.019 | 112.343 | **75.235** | 295.215 |
| datetime_ns_scalar | 3.188 | 3.167 | 3.165 | 2.890 | **0.914** |
| datetime_ns_16 | 3.629 | 3.752 | 3.700 | 3.536 | **2.033** |
| datetime_ns_4096 | 128.354 | 129.343 | 127.983 | **79.771** | 294.210 |
| datetime_us_4096_naive_utc | 118.894 | 118.646 | 119.942 | **82.620** | 264.108 |
| datetime_us_4096_omit_microseconds | 99.983 | 99.087 | 98.154 | **71.443** | 272.744 |
| datetime_us_4096_utc_z | 114.058 | 112.930 | 113.113 | **75.382** | 293.777 |
| datetime_us_4096_naive_utc_omit_microseconds | 103.226 | 102.157 | 101.234 | **71.158** | 278.349 |
| datetime_us_4096_naive_utc_z | 116.810 | 116.497 | 115.938 | **77.572** | 296.686 |
| datetime_us_4096_omit_microseconds_utc_z | 102.218 | 100.637 | 99.173 | **72.138** | 271.670 |
| datetime_us_4096_naive_utc_omit_microseconds_utc_z | 100.538 | 100.195 | 100.209 | **73.890** | 267.989 |
| datetime_us_empty | 2.930 | 2.886 | 2.970 | 3.003 | **0.877** |
| datetime_us_matrix | 113.725 | 113.367 | 114.950 | **75.994** | 297.327 |
| datetime_us_under_dict | 120.988 | 120.150 | 116.693 | **81.254** | 293.554 |

## Public documents

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Rebuilt | Earlier | Selected | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| loads:apache_builds | 316.731 | 306.373 | 265.932 | 273.568 | **233.611** |
| dumps:apache_builds | 118.022 | 118.147 | 119.817 | 123.836 | **58.834** |
| loads:canada | 10,415.774 | 10,013.407 | 10,273.892 | 10,207.149 | **6,512.004** |
| dumps:canada | 5,867.784 | 5,878.846 | 5,925.692 | 5,952.049 | **3,983.635** |
| loads:citm_catalog | 3,756.118 | 3,757.794 | 3,458.819 | 3,597.348 | **2,361.635** |
| dumps:citm_catalog | 1,299.702 | 1,324.401 | 1,277.227 | 1,329.323 | **543.859** |
| loads:github_events | 144.249 | 143.632 | 120.365 | 121.713 | **91.286** |
| dumps:github_events | 51.731 | 53.940 | 51.860 | 52.975 | **24.467** |
| loads:google_maps_api_response | 78.958 | 78.811 | 67.887 | 72.237 | **51.108** |
| dumps:google_maps_api_response | 27.896 | 27.938 | 27.641 | 28.242 | **14.295** |
| loads:gsoc-2018 | 3,640.079 | 3,643.342 | **3,368.600** | 3,384.595 | 4,342.808 |
| dumps:gsoc-2018 | 1,446.324 | 1,472.042 | 1,451.437 | 1,466.474 | **779.898** |
| loads:instruments | 621.890 | 628.472 | 550.571 | 575.175 | **372.017** |
| dumps:instruments | 223.919 | 224.642 | 218.765 | 228.729 | **112.332** |
| loads:marine_ik | 14,244.797 | 14,510.096 | 14,059.316 | 14,077.844 | **11,233.302** |
| dumps:marine_ik | 7,747.520 | 7,759.413 | 8,036.324 | 8,022.450 | **5,031.638** |
| loads:mesh | 2,712.903 | 2,701.800 | 2,668.858 | 2,618.890 | **1,862.657** |
| dumps:mesh | 1,816.610 | 1,822.330 | 1,824.898 | 1,820.821 | **1,305.021** |
| loads:numbers | 416.839 | 418.176 | 420.230 | 407.505 | **272.257** |
| dumps:numbers | 386.911 | 388.817 | 393.718 | 395.268 | **299.749** |
| loads:random | 2,655.544 | 2,651.014 | 2,386.794 | 2,426.857 | **1,685.664** |
| dumps:random | 876.286 | 879.484 | 852.683 | 894.049 | **412.422** |
| loads:semanticscholar-corpus | 32,160.224 | 33,177.519 | 31,132.128 | 30,635.358 | **29,494.885** |
| dumps:semanticscholar-corpus | 9,173.710 | 9,459.869 | 9,222.961 | 9,460.068 | **4,736.622** |
| loads:tree-pretty | 103.463 | 104.177 | 90.274 | 93.467 | **54.492** |
| dumps:tree-pretty | 36.000 | 35.703 | 35.424 | 36.558 | **16.463** |
| loads:twitter | 1,870.678 | 1,876.229 | 1,854.572 | 1,853.329 | **1,058.247** |
| dumps:twitter | 586.360 | 587.015 | 591.464 | 598.295 | **302.048** |
| loads:twitterescaped | 1,867.091 | 1,816.974 | 1,831.629 | 1,872.899 | **1,123.460** |
| dumps:twitterescaped | 598.289 | 601.315 | 598.051 | 616.867 | **308.518** |
| loads:update-center | 1,863.115 | 1,853.135 | 1,663.015 | 1,681.278 | **1,424.464** |
| dumps:update-center | 840.072 | 827.149 | 821.197 | 837.466 | **433.318** |
| loads:poet | 7,624.544 | 7,169.371 | 7,010.574 | 6,955.233 | **4,719.279** |
| dumps:poet | 2,040.517 | 1,944.157 | 2,029.638 | 2,040.109 | **1,007.675** |
| loads:otfcc | 1,024,459.989 | 1,027,378.228 | **776,155.972** | 796,039.791 | 783,070.190 |
| dumps:otfcc | 293,380.613 | 293,265.150 | 277,246.806 | 275,024.154 | **119,850.186** |

## Unequal-output date cases

These cases produce different bytes from orjson 3.11.9 and are not compared here. Their complete timing samples, output sizes and output hashes are retained in results.json.

- time_16
- time_1024
- dates_under_dict

## Sustained regressions

A case qualifies when its paired median time ratio exceeds 1.03 and it takes more than 3% extra time in at least four of five repetitions. Every qualifying case follows, including comparisons between the two controls. Ratios and every repetition remain in results.json; the tables show absolute times.

### jsonmodem baseline rebuild against jsonmodem baseline

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Rebuilt |
| --- | ---: | ---: |
| strings:loads/short_plain/array_view | **0.163** | 0.171 |
| strings:loads/long_escaped/array_view | **61.849** | 64.277 |
| strings:loads/long_escaped/memoryview | **62.424** | 64.892 |
| strings:loads/long_escaped/bytearray | **61.881** | 64.556 |
| frontend:dumps_root_bmp | **11.297** | 11.910 |

### jsonmodem earlier changes against jsonmodem baseline

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Earlier |
| --- | ---: | ---: |
| strings:dumps/unicode_escapes/object | **22.414** | 28.172 |
| frontend:dumps_root_late_quote | **13.356** | 15.221 |
| frontend:dumps_root_early_quote | **13.611** | 15.308 |
| dates:datetime_fixed_offset_16 | **2.299** | 2.455 |
| output:integer_keys | **36.092** | 39.045 |
| strings:loads/long_escaped/memoryview | **62.424** | 66.622 |
| frontend:dumps_root_empty | **0.139** | 0.150 |
| strings:loads/long_escaped/bytes | **58.564** | 63.114 |
| dates:datetime_negative_offset_1024 | **91.342** | 97.465 |
| dates:datetime_fixed_offset_1024 | **91.765** | 99.908 |
| numbers:loads_zero_forms | **0.316** | 0.337 |
| strings:loads/long_escaped/array_view | **61.849** | 65.837 |
| dates:datetime_utc_16 | **1.824** | 1.939 |
| dates:dict_control | **0.264** | 0.279 |
| dates:datetime_seconds_offset_1024 | **91.981** | 97.701 |
| strings:loads/late_escape/bytes | **22.473** | 23.819 |
| frontend:dumps_root_at_threshold | **0.147** | 0.156 |
| strings:loads/long_escaped/bytearray | **61.881** | 65.392 |
| frontend:dumps_root_tiny | **0.154** | 0.160 |
| dates:datetime_utc_1024_omit_microseconds | **58.658** | 60.903 |
| dates:datetime_utc_1024_zero_microseconds | **58.711** | 61.002 |
| dates:datetime_utc_1024 | **66.676** | 69.472 |
| dates:datetime_utc_1024_utc_z | **64.618** | 67.126 |

### jsonmodem selected changes against jsonmodem baseline

Microseconds per complete call; **lower is better**.

| Case | PR #6 | Selected |
| --- | ---: | ---: |
| numbers:loads_zero_forms | **0.316** | 0.352 |
| frontend:loads_small_bytearray | **0.583** | 0.658 |
| frontend:loads_small | **0.564** | 0.623 |
| frontend:loads_small_memoryview | **0.667** | 0.726 |
| frontend:loads_small_array_view | **0.675** | 0.730 |
| dates:list_control | **10.745** | 11.655 |
| numbers:loads_tiny_integers | **0.200** | 0.215 |
| frontend:loads_root_below_threshold | **0.193** | 0.206 |
| output:integer_keys | **36.092** | 38.738 |
| frontend:loads_root_empty | **0.137** | 0.146 |
| dates:uuid_scalar_control | **0.645** | 0.677 |
| numbers:dumps_scalar_integer | **0.076** | 0.082 |
| frontend:loads_root_tiny | **0.158** | 0.167 |
| dates:dict_control | **0.264** | 0.281 |
| strings:dumps/escaped_values/object | **31.965** | 33.912 |
| dates:datetime_fixed_offset_scalar | **0.681** | 0.728 |
| public:dumps:apache_builds | **118.022** | 123.836 |
| dates:date_scalar | **0.602** | 0.632 |
| dates:time_scalar | **0.617** | 0.647 |
| output:escaped | **89.379** | 93.988 |
| numbers:loads_small | **0.313** | 0.327 |
| strings:dumps/medium/object | **145.546** | 150.975 |
| strings:dumps/unique_keys/object | **28.730** | 29.912 |
| public:dumps:marine_ik | **7,747.520** | 8,022.450 |
| output:strings | **22.578** | 23.395 |

### jsonmodem baseline against jsonmodem baseline rebuild

Microseconds per complete call; **lower is better**.

| Case | Rebuilt | PR #6 |
| --- | ---: | ---: |
| output:dataclass_sorted | **565.272** | 630.770 |
| output:dataclass_nested | **516.518** | 577.825 |
| output:dataclass_fields8 | **417.559** | 439.179 |
| output:dataclass_fields16 | **766.004** | 798.631 |

### jsonmodem earlier changes against jsonmodem baseline rebuild

Microseconds per complete call; **lower is better**.

| Case | Rebuilt | Earlier |
| --- | ---: | ---: |
| strings:dumps/unicode_escapes/object | **21.987** | 28.172 |
| strings:loads/late_escape/bytes | **21.515** | 23.819 |
| frontend:dumps_root_late_quote | **13.578** | 15.221 |
| dates:datetime_utc_1024_utc_z | **62.010** | 67.126 |
| frontend:dumps_root_early_quote | **13.803** | 15.308 |
| dates:datetime_utc_1024_omit_microseconds | **58.179** | 60.903 |
| dates:datetime_utc_1024 | **61.954** | 69.472 |
| dates:datetime_naive_1024_naive_utc | **57.187** | 61.169 |
| dates:datetime_utc_1024_zero_microseconds | **55.542** | 61.002 |
| dates:datetime_utc_1024_omit_microseconds_utc_z | **54.962** | 60.175 |
| dates:datetime_naive_1024_naive_utc_z | **54.336** | 58.637 |
| dates:datetime_fixed_offset_1024 | **92.665** | 99.908 |
| dates:datetime_named_zero_offset_1024 | **83.662** | 91.701 |
| dates:datetime_fixed_offset_16 | **2.315** | 2.455 |
| dates:datetime_naive_1024 | **54.582** | 58.134 |
| dates:datetime_naive_1024_omit_microseconds | **49.596** | 51.396 |
| dates:datetime_utc_16 | **1.833** | 1.939 |
| dates:datetime_naive_1024_naive_utc_omit_microseconds | **49.181** | 52.274 |
| dates:datetime_naive_1024_zero_microseconds | **48.558** | 51.398 |
| dates:datetime_naive_1024_naive_utc_omit_microseconds_utc_z | **49.892** | 52.261 |
| numbers:loads_zero_forms | **0.320** | 0.337 |
| dates:datetime_negative_offset_1024 | **90.852** | 97.465 |
| dates:datetime_naive_1024_utc_z | **54.439** | 57.948 |
| frontend:dumps_root_at_threshold | **0.146** | 0.156 |
| dates:datetime_seconds_offset_1024 | **91.085** | 97.701 |
| output:integer_keys | **36.523** | 39.045 |
| dates:datetime_naive_1024_omit_microseconds_utc_z | **49.323** | 51.600 |
| dates:datetime_naive_16 | **1.667** | 1.751 |
| frontend:dumps_root_tiny | **0.154** | 0.160 |
| frontend:dumps_root_empty | **0.143** | 0.150 |
| dates:dict_control | **0.267** | 0.279 |
| frontend:dumps_root_medium | **0.521** | 0.543 |

### jsonmodem selected changes against jsonmodem baseline rebuild

Microseconds per complete call; **lower is better**.

| Case | Rebuilt | Selected |
| --- | ---: | ---: |
| numbers:loads_zero_forms | **0.320** | 0.352 |
| frontend:loads_small | **0.568** | 0.623 |
| frontend:loads_small_bytearray | **0.592** | 0.658 |
| frontend:loads_small_memoryview | **0.660** | 0.726 |
| numbers:loads_tiny_integers | **0.198** | 0.215 |
| frontend:loads_small_array_view | **0.671** | 0.730 |
| strings:dumps/short_plain/object | **0.075** | 0.081 |
| dates:list_control | **10.866** | 11.655 |
| numbers:dumps_scalar_integer | **0.077** | 0.082 |
| strings:dumps/escaped_values/object | **31.652** | 33.912 |
| numbers:loads_small | **0.307** | 0.327 |
| frontend:loads_root_below_threshold | **0.193** | 0.206 |
| strings:dumps/short_escaped/object | **0.085** | 0.091 |
| dates:datetime_fixed_offset_scalar | **0.681** | 0.728 |
| frontend:loads_root_empty | **0.138** | 0.146 |
| output:integer_keys | **36.523** | 38.738 |
| dates:uuid_scalar_control | **0.642** | 0.677 |
| frontend:loads_root_tiny | **0.158** | 0.167 |
| dates:dict_control | **0.267** | 0.281 |
| frontend:dumps_root_at_threshold | **0.146** | 0.155 |
| frontend:loads_root_at_threshold | **0.196** | 0.206 |
| output:escaped | **89.582** | 93.988 |
| output:sorted_medium | **295.899** | 309.220 |
| dates:time_scalar | **0.623** | 0.647 |
| dates:date_scalar | **0.604** | 0.632 |
| public:dumps:marine_ik | **7,759.413** | 8,022.450 |

## Limits

Results apply to these cases and recorded library/interpreter versions. A favorable mean does not establish a universal advantage or memory-safety equivalence. This export contains no RSS, allocation or streaming measurements; those require separate exports.
