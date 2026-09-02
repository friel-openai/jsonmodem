# Complete-call benchmark results

The selected build is runtime revision `96318df`; the baseline is PR #6.
The reference is orjson 3.11.9. Version 3.12.0 was not measured.

These results measure complete loads() and dumps() calls. Bold marks every exact row minimum, including ties.

The baseline, its unchanged rebuild, the earlier changes and the selected changes are identified by their built runtime revisions in results.json. A later publication revision, when supplied, is recorded separately and is not the revision measured.

Each suite and jsonmodem build ran in five fresh Python processes. Each process recorded three samples for jsonmodem and orjson. Each jsonmodem cell uses the median of five process medians. The displayed orjson cell uses all twenty reference process medians, five per jsonmodem build. All raw samples and paired comparisons remain in results.json.

The geometric means weight each comparable case equally. They summarize case latencies, not elapsed time to execute a suite. The three unequal-output date cases are excluded from all means, win counts and regression comparisons, matching the validated comparison.

## Overall and suite means

Microseconds per complete call; **lower is better**.

| Geometric mean | jsonmodem baseline | jsonmodem baseline rebuild | jsonmodem earlier changes | jsonmodem selected changes | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall (275 comparable cases) | 44.521 | 44.775 | 43.635 | 43.020 | **35.111** |
| Encoding (28 cases) | 65.007 | 64.637 | 63.222 | 63.463 | **38.456** |
| Complete-call inputs (58 cases) | 19.527 | 19.559 | **19.139** | 20.900 | 19.271 |
| Numbers (25 cases) | 38.247 | 38.461 | 38.480 | 38.515 | **30.659** |
| Strings (60 cases) | 28.509 | 28.757 | 27.257 | 27.310 | **23.321** |
| Dates (40 cases) | 18.176 | 18.679 | 18.561 | 15.852 | **11.802** |
| NumPy dates (28 cases) | 21.042 | 21.073 | 20.983 | **17.475** | 22.946 |
| Public documents (36 cases) | 1,416.591 | 1,410.373 | 1,347.626 | 1,431.645 | **873.624** |

## Encoding

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem baseline rebuild | jsonmodem earlier changes | jsonmodem selected changes | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| small | 0.3729 | 0.3727 | 0.3704 | 0.3908 | **0.2572** |
| medium | 146.882 | 147.746 | 147.205 | 146.202 | **90.271** |
| integers | 109.251 | 107.898 | 106.304 | 107.090 | **44.352** |
| floats | 314.386 | 314.234 | 317.228 | 317.633 | **294.339** |
| strings | 23.494 | 22.469 | 21.688 | 23.135 | **13.823** |
| escaped | 90.049 | 89.002 | 90.621 | 106.459 | **41.680** |
| long_string | 12.183 | 12.203 | 12.158 | 12.100 | **10.246** |
| integers_wide_signed | 247.976 | 249.706 | 245.438 | **241.932** | 353.500 |
| integers_wide_unsigned | 198.969 | 200.817 | **196.024** | 209.919 | 332.444 |
| scalar_integer | 0.1689 | 0.1727 | **0.1595** | 0.1597 | 0.1642 |
| integers_tiny | 0.248 | 0.251 | 0.239 | 0.245 | **0.200** |
| indent_integers | 137.972 | 136.176 | 132.591 | 135.801 | **84.345** |
| strict_integers | 114.908 | 114.861 | 113.789 | 113.493 | **44.483** |
| sorted_medium | 300.894 | 295.341 | 303.657 | 279.181 | **131.986** |
| integer_keys | 36.023 | 36.394 | 38.865 | 39.406 | **35.244** |
| dataclasses | 194.839 | 196.469 | 191.689 | 184.245 | **77.939** |
| dataclass_single | 0.945 | 0.946 | 0.949 | 0.960 | **0.261** |
| dataclass_slots_single | 1.5133 | 1.5132 | 1.5008 | 1.5002 | **0.6248** |
| dataclass_slots | 736.924 | 737.580 | 708.899 | 712.299 | **374.998** |
| dataclass_nested | 577.172 | 527.097 | 526.421 | 497.164 | **195.057** |
| dataclass_indent | 209.508 | 209.870 | 202.509 | 200.624 | **105.341** |
| dataclass_sorted | 626.412 | 575.475 | 564.286 | 528.394 | **216.417** |
| dataclass_default | 263.162 | 266.462 | 255.281 | 274.497 | **127.999** |
| numpy_int64 | 920.992 | 921.514 | 928.401 | **920.619** | 1,340.078 |
| numpy_float32 | 2,823.460 | 2,805.082 | 2,793.093 | **2,784.893** | 3,258.839 |
| late_default | 9.783 | 10.101 | 9.099 | 8.502 | **3.167** |
| dataclass_fields8 | 416.333 | 417.379 | 383.974 | 377.283 | **174.191** |
| dataclass_fields16 | 774.830 | 774.138 | 687.916 | 672.072 | **304.305** |

## Complete-call inputs

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem baseline rebuild | jsonmodem earlier changes | jsonmodem selected changes | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| loads_small | 0.578 | 0.553 | 0.557 | 0.646 | **0.520** |
| loads_small_bytearray | 0.590 | 0.588 | 0.587 | 0.660 | **0.524** |
| loads_small_memoryview | 0.678 | 0.666 | 0.664 | 0.740 | **0.526** |
| loads_small_array_view | 0.676 | 0.666 | 0.660 | 0.738 | **0.526** |
| loads_medium | 361.300 | 360.675 | 304.746 | 316.449 | **243.172** |
| loads_medium_bytearray | 366.179 | 367.375 | 314.863 | 327.311 | **243.612** |
| loads_medium_memoryview | 364.793 | 372.086 | 309.321 | 318.396 | **243.615** |
| loads_medium_array_view | 364.980 | 370.592 | 313.667 | 323.178 | **244.830** |
| loads_integers | 255.950 | 258.646 | 259.649 | 252.006 | **189.766** |
| loads_integers_bytearray | 260.546 | 260.751 | 261.346 | 254.577 | **189.166** |
| loads_integers_memoryview | 261.435 | 260.501 | 262.395 | 254.887 | **190.043** |
| loads_integers_array_view | 261.446 | 259.904 | 262.688 | 256.960 | **189.316** |
| loads_floats | 463.247 | 462.206 | 468.932 | 456.883 | **280.618** |
| loads_floats_bytearray | 470.770 | 471.006 | 478.084 | 464.045 | **279.500** |
| loads_floats_memoryview | 471.759 | 470.204 | 474.538 | 462.879 | **279.264** |
| loads_floats_array_view | 471.569 | 471.787 | 471.408 | 461.317 | **279.518** |
| loads_strings | 39.350 | 39.122 | 39.883 | 37.880 | **36.714** |
| loads_strings_bytearray | 40.509 | 40.575 | 40.699 | 38.781 | **36.752** |
| loads_strings_memoryview | 40.759 | 40.339 | 41.085 | 38.985 | **36.636** |
| loads_strings_array_view | 40.512 | 40.293 | 40.889 | 38.896 | **36.763** |
| loads_escaped | 249.967 | 250.054 | 235.551 | 242.368 | **143.868** |
| loads_escaped_bytearray | 251.251 | 250.502 | 235.041 | 246.164 | **143.307** |
| loads_escaped_memoryview | 253.323 | 251.754 | 236.728 | 245.633 | **143.308** |
| loads_escaped_array_view | 251.348 | 250.947 | 235.401 | 245.876 | **142.954** |
| loads_long_string | 16.752 | 16.702 | 16.788 | **14.268** | 92.962 |
| loads_long_string_bytearray | 21.160 | 20.995 | 21.905 | **18.726** | 93.288 |
| loads_long_string_memoryview | 21.311 | 21.657 | 21.753 | **18.498** | 93.069 |
| loads_long_string_array_view | 21.131 | 20.859 | 21.588 | **18.332** | 92.896 |
| dumps_root_empty | **0.139** | 0.141 | 0.150 | 0.146 | 0.157 |
| loads_root_empty | 0.1384 | 0.1376 | 0.1344 | 0.1372 | **0.0928** |
| dumps_root_tiny | 0.153 | **0.152** | 0.159 | 0.156 | 0.157 |
| loads_root_tiny | **0.156** | 0.158 | 0.157 | 0.160 | 0.207 |
| dumps_root_below_threshold | 0.2626 | 0.2632 | 0.2737 | 0.2629 | **0.2620** |
| loads_root_below_threshold | 0.192 | 0.193 | 0.196 | **0.190** | 0.271 |
| dumps_root_at_threshold | 0.147 | **0.146** | 0.157 | 0.160 | 0.256 |
| loads_root_at_threshold | 0.1944 | 0.1970 | 0.2005 | **0.1942** | 0.2719 |
| dumps_root_medium | 0.5223 | 0.5356 | 0.5427 | 0.5430 | **0.5212** |
| loads_root_medium | 0.675 | 0.671 | 0.697 | **0.610** | 1.485 |
| dumps_root_long | 11.092 | 11.063 | 11.226 | 11.045 | **9.114** |
| loads_root_long | 15.316 | 15.335 | 15.426 | **12.946** | 85.183 |
| dumps_root_early_quote | 15.091 | 15.271 | 13.826 | 13.616 | **9.048** |
| loads_root_early_quote | 18.874 | 19.030 | 19.809 | **18.055** | 90.158 |
| dumps_root_late_quote | 15.440 | 15.216 | 13.927 | 13.671 | **9.144** |
| loads_root_late_quote | 18.882 | 18.711 | 19.750 | **17.918** | 84.984 |
| dumps_root_dense_escapes | 83.898 | 85.747 | **82.563** | 87.563 | 189.161 |
| loads_root_dense_escapes | 121.882 | 120.843 | 121.288 | 118.809 | **116.621** |
| dumps_root_latin1 | 11.209 | 11.752 | 11.568 | 82.772 | **8.613** |
| loads_root_latin1 | 98.548 | 100.749 | 98.681 | 98.525 | **93.944** |
| dumps_root_bmp | 11.166 | 11.700 | 11.811 | 93.220 | **8.587** |
| loads_root_bmp | 97.669 | 97.724 | 97.871 | 97.661 | **82.549** |
| dumps_root_non_bmp | 12.009 | 12.013 | 11.818 | 83.231 | **8.618** |
| loads_root_non_bmp | 86.724 | 86.842 | 86.872 | 86.978 | **66.500** |
| dumps_root_append_newline | 11.167 | 11.208 | 11.361 | 11.272 | **9.174** |
| dumps_root_indent | 11.104 | 11.228 | 11.334 | 11.340 | **9.160** |
| loads_escaped_values | 55.172 | 55.102 | 56.140 | 54.551 | **34.273** |
| loads_unicode_escapes | 138.105 | 140.034 | 137.544 | 134.131 | **45.887** |
| loads_repeated_escaped_keys | 123.235 | 121.472 | 111.102 | 120.538 | **87.272** |
| loads_unique_escaped_keys | 143.016 | 142.940 | 78.126 | 77.447 | **36.798** |

## Numbers

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem baseline rebuild | jsonmodem earlier changes | jsonmodem selected changes | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| loads_small | 0.303 | 0.304 | 0.311 | 0.336 | **0.261** |
| loads_medium | 290.985 | 292.861 | 250.860 | 265.585 | **194.393** |
| loads_integers | 255.895 | 256.970 | 259.436 | 254.916 | **186.626** |
| loads_random_small | 311.329 | 315.259 | 319.406 | 313.908 | **241.039** |
| loads_wide_signed | 429.681 | 442.509 | 441.302 | 437.142 | **349.997** |
| loads_wide_unsigned | 380.940 | 388.387 | 388.027 | 375.442 | **272.472** |
| loads_mixed_integers | 438.568 | 443.517 | 450.821 | 444.995 | **348.561** |
| loads_tiny_integers | **0.1992** | 0.2001 | 0.2102 | 0.2180 | 0.1995 |
| loads_scalar_integer | 0.082 | 0.083 | 0.081 | **0.078** | 0.115 |
| loads_floats | 463.436 | 464.403 | 468.368 | 457.226 | **278.272** |
| loads_float_bits | 694.189 | 698.059 | 700.465 | 694.763 | **429.531** |
| loads_overflow_integers | 909.976 | 911.661 | 922.431 | 952.356 | **660.465** |
| loads_long_fractions | 727.419 | 728.162 | 738.894 | 758.453 | **440.195** |
| loads_zero_forms | 0.3135 | 0.3143 | 0.3380 | 0.3449 | **0.2258** |
| dumps_small | 0.166 | 0.167 | 0.174 | 0.168 | **0.112** |
| dumps_medium | 125.997 | 126.585 | 129.363 | 127.051 | **79.619** |
| dumps_integers | 108.434 | 109.174 | 107.604 | 107.778 | **44.682** |
| dumps_random_small | 159.726 | 159.205 | 154.444 | 154.200 | **76.638** |
| dumps_wide_signed | 250.422 | 250.393 | 251.492 | **246.792** | 360.159 |
| dumps_wide_unsigned | 204.077 | **201.690** | 202.244 | 211.993 | 337.560 |
| dumps_mixed_integers | 257.959 | 256.192 | 255.597 | **254.156** | 361.092 |
| dumps_tiny_integers | 0.143 | 0.148 | 0.138 | 0.136 | **0.108** |
| dumps_scalar_integer | **0.0760** | 0.0763 | 0.0788 | 0.0762 | 0.0796 |
| dumps_floats | 320.433 | 319.853 | 323.317 | 321.302 | **299.304** |
| dumps_float_bits | 398.575 | 399.896 | 390.495 | 393.818 | **309.839** |

## Strings

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem baseline rebuild | jsonmodem earlier changes | jsonmodem selected changes | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| loads/short_plain/bytes | 0.092 | 0.093 | **0.082** | 0.096 | 0.121 |
| loads/short_plain/bytearray | 0.1070 | 0.1082 | **0.0992** | 0.1085 | 0.1242 |
| loads/short_plain/memoryview | 0.1617 | 0.1695 | 0.1640 | 0.1638 | **0.1254** |
| loads/short_plain/array_view | 0.1622 | 0.1725 | 0.1623 | 0.1640 | **0.1254** |
| dumps/short_plain/object | **0.0735** | 0.0747 | 0.0776 | 0.0784 | 0.0804 |
| loads/short_escaped/bytes | 0.130 | 0.131 | **0.123** | 0.136 | 0.129 |
| loads/short_escaped/bytearray | 0.144 | 0.145 | 0.141 | 0.148 | **0.131** |
| loads/short_escaped/memoryview | 0.220 | 0.222 | 0.212 | 0.213 | **0.132** |
| loads/short_escaped/array_view | 0.2201 | 0.2205 | 0.2120 | 0.2140 | **0.1317** |
| dumps/short_escaped/object | 0.0849 | **0.0842** | 0.0869 | 0.0866 | 0.0843 |
| loads/plain_values/bytes | 39.107 | 39.252 | 39.837 | 38.625 | **36.368** |
| loads/plain_values/bytearray | 39.815 | 40.309 | 40.531 | 39.427 | **36.390** |
| loads/plain_values/memoryview | 40.159 | 40.264 | 40.628 | 39.796 | **36.450** |
| loads/plain_values/array_view | 39.576 | 40.448 | 40.700 | 39.798 | **36.449** |
| dumps/plain_values/object | 22.814 | 22.768 | 21.625 | 22.234 | **13.940** |
| loads/escaped_values/bytes | 65.606 | 66.024 | 67.171 | 65.874 | **37.702** |
| loads/escaped_values/bytearray | 65.941 | 66.659 | 67.693 | 66.500 | **37.826** |
| loads/escaped_values/memoryview | 66.139 | 66.616 | 67.966 | 66.840 | **37.795** |
| loads/escaped_values/array_view | 66.226 | 66.370 | 68.209 | 67.181 | **37.950** |
| dumps/escaped_values/object | 31.601 | 31.745 | 33.309 | 33.095 | **23.230** |
| loads/unicode_escapes/bytes | 142.914 | 144.942 | 143.078 | 141.893 | **55.067** |
| loads/unicode_escapes/bytearray | 141.977 | 143.267 | 147.103 | 143.714 | **55.514** |
| loads/unicode_escapes/memoryview | 141.803 | 142.382 | 144.051 | 144.872 | **55.236** |
| loads/unicode_escapes/array_view | 142.447 | 143.789 | 143.267 | 143.528 | **55.097** |
| dumps/unicode_escapes/object | 21.979 | 22.174 | 28.451 | 39.837 | **11.829** |
| loads/escaped_keys/bytes | 311.766 | 319.903 | 301.439 | 315.409 | **171.034** |
| loads/escaped_keys/bytearray | 317.079 | 316.262 | 301.060 | 316.095 | **171.096** |
| loads/escaped_keys/memoryview | 320.370 | 315.645 | 302.985 | 315.801 | **171.531** |
| loads/escaped_keys/array_view | 316.558 | 313.452 | 301.262 | 318.103 | **171.877** |
| dumps/escaped_keys/object | 91.516 | 91.670 | 94.215 | 103.673 | **47.165** |
| loads/unique_keys/bytes | 159.317 | 157.484 | 99.614 | 97.970 | **47.945** |
| loads/unique_keys/bytearray | 159.216 | 159.497 | 99.931 | 98.013 | **47.838** |
| loads/unique_keys/memoryview | 158.516 | 159.024 | 99.857 | 98.467 | **48.058** |
| loads/unique_keys/array_view | 158.536 | 159.894 | 100.344 | 98.201 | **47.965** |
| dumps/unique_keys/object | 28.843 | 29.848 | 27.267 | 28.320 | **12.496** |
| loads/long_plain/bytes | 17.133 | 17.162 | 17.114 | **14.618** | 95.572 |
| loads/long_plain/bytearray | 21.575 | 21.663 | 21.489 | **18.402** | 95.054 |
| loads/long_plain/memoryview | 21.035 | 21.693 | 21.177 | **18.500** | 95.298 |
| loads/long_plain/array_view | 21.301 | 22.101 | 21.365 | **18.614** | 95.255 |
| dumps/long_plain/object | 12.481 | 12.718 | 12.427 | 12.430 | **10.194** |
| loads/long_escaped/bytes | 61.279 | 61.498 | 58.564 | **56.887** | 100.093 |
| loads/long_escaped/bytearray | 64.240 | 65.034 | 63.125 | **62.251** | 100.062 |
| loads/long_escaped/memoryview | 63.843 | 64.566 | 62.548 | **60.527** | 100.047 |
| loads/long_escaped/array_view | 63.771 | 64.827 | 62.641 | **60.948** | 100.241 |
| dumps/long_escaped/object | 46.897 | 48.238 | **46.527** | 48.945 | 50.782 |
| loads/late_escape/bytes | 22.130 | 22.219 | 21.134 | **18.649** | 95.399 |
| loads/late_escape/bytearray | 71.801 | 73.322 | 71.439 | **70.233** | 95.338 |
| loads/late_escape/memoryview | 71.972 | 73.095 | 71.477 | **69.899** | 95.361 |
| loads/late_escape/array_view | 71.405 | 73.359 | 72.059 | **68.979** | 95.459 |
| dumps/late_escape/object | 15.273 | 14.820 | 15.292 | 15.124 | **10.228** |
| loads/medium/bytes | 363.144 | 365.560 | 312.828 | 331.900 | **249.259** |
| loads/medium/bytearray | 360.584 | 369.565 | 311.585 | 326.997 | **248.515** |
| loads/medium/memoryview | 368.366 | 371.751 | 312.301 | 327.981 | **249.315** |
| loads/medium/array_view | 362.813 | 374.034 | 310.592 | 328.883 | **248.859** |
| dumps/medium/object | 147.707 | 148.231 | 147.874 | 147.042 | **90.773** |
| loads/integers/bytes | 263.220 | 256.236 | 257.635 | 251.862 | **187.653** |
| loads/integers/bytearray | 265.421 | 266.245 | 260.149 | 256.190 | **189.464** |
| loads/integers/memoryview | 265.933 | 259.340 | 258.987 | 254.596 | **188.626** |
| loads/integers/array_view | 265.337 | 259.906 | 258.193 | 255.193 | **188.154** |
| dumps/integers/object | 107.908 | 107.899 | 106.454 | 105.651 | **44.629** |

## Dates

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem baseline rebuild | jsonmodem earlier changes | jsonmodem selected changes | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| datetime_naive_scalar | 0.622 | 0.628 | 0.637 | 0.650 | **0.198** |
| datetime_naive_16 | 1.684 | 1.681 | 1.705 | 1.580 | **0.620** |
| datetime_naive_1024 | 54.897 | 56.786 | 56.355 | 41.713 | **30.184** |
| datetime_utc_scalar | 0.649 | 0.631 | 0.645 | 0.654 | **0.276** |
| datetime_utc_16 | 1.751 | 1.846 | 1.893 | **1.714** | 1.735 |
| datetime_utc_1024 | 60.827 | 66.832 | 64.578 | **50.414** | 101.122 |
| datetime_fixed_offset_scalar | 0.690 | 0.686 | 0.699 | 0.709 | **0.288** |
| datetime_fixed_offset_16 | 2.289 | 2.326 | 2.441 | 2.208 | **1.855** |
| datetime_fixed_offset_1024 | 90.162 | 92.612 | 96.380 | **77.669** | 110.305 |
| date_scalar | 0.600 | 0.609 | 0.634 | 0.629 | **0.189** |
| date_16 | 1.296 | 1.310 | 1.321 | 1.159 | **0.446** |
| date_1024 | 40.082 | 40.380 | 40.093 | 27.719 | **18.216** |
| time_scalar | 0.616 | 0.618 | 0.649 | 0.640 | **0.198** |
| datetime_naive_1024_zero_microseconds | 47.251 | 50.231 | 48.739 | 36.308 | **24.367** |
| datetime_utc_1024_zero_microseconds | 55.333 | 58.658 | 55.039 | **41.026** | 92.995 |
| time_1024_zero_microseconds | 49.444 | 50.464 | 49.424 | 38.257 | **19.993** |
| datetime_naive_1024_naive_utc | 55.484 | 58.952 | 59.062 | 43.703 | **32.566** |
| datetime_naive_1024_omit_microseconds | 47.490 | 50.193 | 48.495 | 36.463 | **23.186** |
| datetime_naive_1024_utc_z | 53.456 | 56.756 | 54.567 | 41.950 | **29.799** |
| datetime_naive_1024_naive_utc_omit_microseconds | 48.787 | 50.675 | 47.829 | 37.112 | **25.546** |
| datetime_naive_1024_naive_utc_z | 54.910 | 56.996 | 54.755 | 42.734 | **31.584** |
| datetime_naive_1024_omit_microseconds_utc_z | 47.549 | 50.344 | 48.421 | 36.523 | **23.207** |
| datetime_naive_1024_naive_utc_omit_microseconds_utc_z | 48.414 | 50.487 | 49.057 | 37.480 | **25.390** |
| datetime_utc_1024_omit_microseconds | 55.198 | 58.639 | 54.974 | **41.312** | 92.934 |
| datetime_utc_1024_utc_z | 58.623 | 64.743 | 62.480 | **48.713** | 98.935 |
| datetime_utc_1024_omit_microseconds_utc_z | 54.929 | 58.028 | 56.768 | **41.411** | 91.832 |
| time_1024_omit_microseconds | 49.601 | 50.907 | 49.460 | 37.836 | **19.610** |
| date_1024_options | 40.532 | 40.411 | 40.136 | 27.980 | **18.325** |
| dataclass_dates | 234.925 | 232.485 | 235.078 | 222.909 | **189.594** |
| datetime_passthrough | 914.974 | 909.633 | 913.555 | 919.872 | **663.252** |
| datetime_subclass | 747.438 | 745.127 | 741.053 | 731.097 | **696.715** |
| datetime_named_zero_offset_1024 | 83.521 | 87.963 | 89.253 | **74.261** | 100.503 |
| datetime_negative_offset_1024 | 90.233 | 92.471 | 95.457 | **77.465** | 109.766 |
| datetime_seconds_offset_1024 | 91.511 | 93.079 | 96.553 | **76.251** | 109.490 |
| uuid_scalar_control | 0.652 | 0.657 | 0.666 | 0.678 | **0.228** |
| uuid_list_control | 79.006 | 79.129 | 80.428 | 80.620 | **46.134** |
| dict_control | 0.262 | 0.269 | 0.280 | 0.297 | **0.224** |
| list_control | 10.763 | 10.943 | 9.816 | 10.423 | **4.411** |
| string_control | 0.1672 | 0.1697 | 0.1670 | **0.1638** | 0.1742 |
| dataclass_control | 204.782 | 202.506 | 199.857 | 199.067 | **83.415** |

## NumPy dates

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem baseline rebuild | jsonmodem earlier changes | jsonmodem selected changes | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| datetime_Y_scalar | 3.225 | 3.102 | 3.083 | 2.793 | **0.878** |
| datetime_Y_16 | 3.428 | 3.436 | 3.434 | 3.489 | **1.920** |
| datetime_Y_4096 | 71.598 | 71.974 | **70.794** | 75.674 | 266.296 |
| datetime_M_scalar | 3.139 | 3.104 | 3.079 | 2.781 | **0.871** |
| datetime_M_16 | 3.517 | 3.510 | 3.491 | 3.526 | **1.970** |
| datetime_M_4096 | **80.224** | 81.719 | 80.853 | 82.668 | 281.097 |
| datetime_D_scalar | 3.110 | 3.083 | 3.091 | 2.773 | **0.870** |
| datetime_D_16 | 3.567 | 3.559 | 3.664 | 3.597 | **1.916** |
| datetime_D_4096 | 107.143 | 107.591 | 107.058 | **103.993** | 267.434 |
| datetime_s_scalar | 3.096 | 3.138 | 3.061 | 2.779 | **0.866** |
| datetime_s_16 | 3.559 | 3.504 | 3.536 | 3.461 | **1.934** |
| datetime_s_4096 | 101.515 | 102.123 | 102.520 | **69.737** | 275.828 |
| datetime_us_scalar | 3.143 | 3.166 | 3.174 | 2.860 | **0.900** |
| datetime_us_16 | 3.599 | 3.572 | 3.644 | 3.482 | **2.029** |
| datetime_us_4096 | 112.556 | 112.590 | 112.487 | **75.485** | 294.861 |
| datetime_ns_scalar | 3.154 | 3.189 | 3.193 | 2.878 | **0.908** |
| datetime_ns_16 | 3.644 | 3.650 | 3.703 | 3.518 | **2.032** |
| datetime_ns_4096 | 128.386 | 128.264 | 126.230 | **79.392** | 294.444 |
| datetime_us_4096_naive_utc | 119.551 | 121.168 | 120.887 | **82.749** | 264.377 |
| datetime_us_4096_omit_microseconds | 99.186 | 101.638 | 98.392 | **71.503** | 272.662 |
| datetime_us_4096_utc_z | 113.400 | 113.573 | 112.041 | **75.776** | 294.546 |
| datetime_us_4096_naive_utc_omit_microseconds | 101.958 | 102.541 | 101.551 | **71.935** | 277.577 |
| datetime_us_4096_naive_utc_z | 115.923 | 116.046 | 116.510 | **77.226** | 297.059 |
| datetime_us_4096_omit_microseconds_utc_z | 99.393 | 100.461 | 98.979 | **72.583** | 271.290 |
| datetime_us_4096_naive_utc_omit_microseconds_utc_z | 100.176 | 101.813 | 98.907 | **73.402** | 267.616 |
| datetime_us_empty | 2.941 | 2.890 | 2.981 | 2.992 | **0.868** |
| datetime_us_matrix | 113.552 | 113.565 | 112.448 | **76.495** | 297.493 |
| datetime_us_under_dict | 120.195 | 120.579 | 116.779 | **80.323** | 293.600 |

## Public documents

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem baseline rebuild | jsonmodem earlier changes | jsonmodem selected changes | orjson 3.11.9 |
| --- | ---: | ---: | ---: | ---: | ---: |
| loads:apache_builds | 309.763 | 298.005 | 265.953 | 268.596 | **234.892** |
| dumps:apache_builds | 118.144 | 116.755 | 118.668 | 122.033 | **58.294** |
| loads:canada | 9,785.108 | 10,327.101 | 10,212.283 | 9,695.876 | **6,570.014** |
| dumps:canada | 5,857.984 | 5,857.379 | 5,926.102 | 5,994.017 | **3,969.406** |
| loads:citm_catalog | 3,755.134 | 3,816.476 | 3,419.139 | 3,564.322 | **2,342.489** |
| dumps:citm_catalog | 1,257.849 | 1,276.785 | 1,280.240 | 1,368.579 | **543.422** |
| loads:github_events | 142.699 | 142.417 | 119.713 | 122.633 | **91.575** |
| dumps:github_events | 52.374 | 52.194 | 51.568 | 53.088 | **24.621** |
| loads:google_maps_api_response | 78.474 | 79.286 | 67.169 | 71.562 | **50.969** |
| dumps:google_maps_api_response | 27.910 | 27.746 | 27.448 | 28.455 | **14.235** |
| loads:gsoc-2018 | 3,729.380 | 3,687.481 | 3,424.617 | **3,379.060** | 5,264.361 |
| dumps:gsoc-2018 | 1,470.860 | 1,492.546 | 1,447.251 | 1,536.683 | **789.646** |
| loads:instruments | 630.455 | 626.146 | 550.491 | 571.068 | **373.042** |
| dumps:instruments | 224.698 | 221.341 | 222.183 | 228.184 | **112.447** |
| loads:marine_ik | 14,904.480 | 14,393.200 | 14,043.383 | **13,914.707** | 13,949.424 |
| dumps:marine_ik | 7,851.565 | 7,724.671 | 7,653.543 | 7,877.326 | **5,011.737** |
| loads:mesh | 2,689.436 | 2,704.782 | 2,758.787 | 2,635.384 | **1,848.585** |
| dumps:mesh | 1,808.663 | 1,811.483 | 1,791.033 | 1,824.973 | **1,298.858** |
| loads:numbers | 415.604 | 417.070 | 420.425 | 409.230 | **271.171** |
| dumps:numbers | 387.091 | 389.844 | 396.084 | 397.968 | **300.091** |
| loads:random | 2,706.240 | 2,675.433 | 2,367.695 | 2,474.076 | **1,689.379** |
| dumps:random | 850.071 | 843.843 | 829.753 | 989.905 | **410.882** |
| loads:semanticscholar-corpus | 29,832.695 | 29,347.272 | 28,600.668 | **28,311.311** | 34,985.938 |
| dumps:semanticscholar-corpus | 9,067.860 | 9,138.147 | 9,025.020 | 9,950.903 | **4,627.821** |
| loads:tree-pretty | 103.677 | 103.969 | 88.852 | 94.192 | **54.437** |
| dumps:tree-pretty | 35.824 | 35.653 | 34.364 | 37.470 | **16.480** |
| loads:twitter | 1,880.347 | 1,876.089 | 1,853.179 | 1,845.749 | **1,056.713** |
| dumps:twitter | 585.813 | 588.824 | 589.092 | 710.232 | **300.890** |
| loads:twitterescaped | 1,840.506 | 1,844.827 | 1,827.596 | 1,830.292 | **1,123.485** |
| dumps:twitterescaped | 602.445 | 593.918 | 589.146 | 726.076 | **306.808** |
| loads:update-center | 1,871.234 | 1,867.225 | 1,671.164 | 1,674.360 | **1,429.328** |
| dumps:update-center | 833.830 | 817.756 | 811.933 | 845.036 | **429.901** |
| loads:poet | 7,168.076 | 7,274.397 | 6,788.355 | 7,112.530 | **4,623.953** |
| dumps:poet | 1,961.352 | 1,917.412 | 1,921.786 | 4,448.267 | **1,013.032** |
| loads:otfcc | 1,025,654.663 | 992,763.201 | **764,111.927** | 796,748.135 | 892,332.203 |
| dumps:otfcc | 379,879.956 | 365,255.961 | 367,771.465 | 376,285.870 | **153,596.242** |

## Unequal-output date cases

These cases produce different bytes from orjson 3.11.9 and are not compared here. Their complete timing samples, output sizes and output hashes are retained in results.json.

- time_16
- time_1024
- dates_under_dict

## Sustained regressions

A case qualifies when its paired median time ratio exceeds 1.03 and it takes more than 3% extra time in at least four of five repetitions. Every qualifying case follows, including comparisons between the two controls. Ratios and every repetition remain in results.json; the tables show absolute times.

### jsonmodem baseline rebuild against jsonmodem baseline

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem baseline rebuild |
| --- | ---: | ---: |
| dates:datetime_utc_1024_utc_z | **58.623** | 64.743 |
| dates:datetime_utc_1024 | **60.827** | 66.832 |
| dates:datetime_utc_1024_omit_microseconds_utc_z | **54.929** | 58.028 |
| dates:datetime_naive_1024_utc_z | **53.456** | 56.756 |
| dates:datetime_naive_1024_omit_microseconds | **47.490** | 50.193 |
| dates:datetime_utc_1024_omit_microseconds | **55.198** | 58.639 |
| dates:datetime_naive_1024_naive_utc | **55.484** | 58.952 |
| dates:datetime_naive_1024_omit_microseconds_utc_z | **47.549** | 50.344 |
| dates:datetime_utc_1024_zero_microseconds | **55.333** | 58.658 |
| dates:datetime_naive_1024_zero_microseconds | **47.251** | 50.231 |
| strings:loads/short_plain/array_view | **0.162** | 0.173 |
| dates:datetime_named_zero_offset_1024 | **83.521** | 87.963 |
| strings:loads/short_plain/memoryview | **0.162** | 0.170 |
| dates:datetime_utc_16 | **1.751** | 1.846 |
| frontend:dumps_root_latin1 | **11.209** | 11.752 |

### jsonmodem earlier changes against jsonmodem baseline

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem earlier changes |
| --- | ---: | ---: |
| strings:dumps/unicode_escapes/object | **21.979** | 28.451 |
| output:integer_keys | **36.023** | 38.865 |
| frontend:dumps_root_empty | **0.139** | 0.150 |
| dates:datetime_utc_16 | **1.751** | 1.893 |
| numbers:loads_zero_forms | **0.314** | 0.338 |
| dates:datetime_fixed_offset_1024 | **90.162** | 96.380 |
| frontend:dumps_root_at_threshold | **0.147** | 0.157 |
| dates:datetime_utc_1024 | **60.827** | 64.578 |
| dates:dict_control | **0.262** | 0.280 |
| dates:datetime_named_zero_offset_1024 | **83.521** | 89.253 |
| dates:datetime_fixed_offset_16 | **2.289** | 2.441 |
| strings:dumps/short_plain/object | **0.073** | 0.078 |
| strings:dumps/escaped_values/object | **31.601** | 33.309 |
| dates:datetime_negative_offset_1024 | **90.233** | 95.457 |
| dates:datetime_utc_1024_utc_z | **58.623** | 62.480 |
| frontend:dumps_root_bmp | **11.166** | 11.811 |
| numbers:dumps_small | **0.166** | 0.174 |
| frontend:dumps_root_below_threshold | **0.263** | 0.274 |
| frontend:dumps_root_tiny | **0.153** | 0.159 |
| dates:datetime_seconds_offset_1024 | **91.511** | 96.553 |
| frontend:loads_root_early_quote | **18.874** | 19.809 |
| numbers:loads_tiny_integers | **0.199** | 0.210 |
| dates:uuid_scalar_control | **0.652** | 0.666 |

### jsonmodem selected changes against jsonmodem baseline

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline | jsonmodem selected changes |
| --- | ---: | ---: |
| frontend:dumps_root_bmp | **11.166** | 93.220 |
| frontend:dumps_root_latin1 | **11.209** | 82.772 |
| frontend:dumps_root_non_bmp | **12.009** | 83.231 |
| public:dumps:poet | **1,961.352** | 4,448.267 |
| strings:dumps/unicode_escapes/object | **21.979** | 39.837 |
| public:dumps:twitterescaped | **602.445** | 726.076 |
| public:dumps:twitter | **585.813** | 710.232 |
| output:escaped | **90.049** | 106.459 |
| public:dumps:random | **850.071** | 989.905 |
| dates:dict_control | **0.262** | 0.297 |
| strings:dumps/escaped_keys/object | **91.516** | 103.673 |
| frontend:loads_small_bytearray | **0.590** | 0.660 |
| frontend:loads_small | **0.578** | 0.646 |
| numbers:loads_small | **0.303** | 0.336 |
| frontend:loads_small_memoryview | **0.678** | 0.740 |
| frontend:dumps_root_at_threshold | **0.147** | 0.160 |
| public:dumps:semanticscholar-corpus | **9,067.860** | 9,950.903 |
| numbers:loads_zero_forms | **0.314** | 0.345 |
| public:dumps:citm_catalog | **1,257.849** | 1,368.579 |
| frontend:loads_small_array_view | **0.676** | 0.738 |
| numbers:loads_tiny_integers | **0.199** | 0.218 |
| output:integer_keys | **36.023** | 39.406 |
| numpy:datetime_Y_4096 | **71.598** | 75.674 |
| strings:dumps/short_plain/object | **0.073** | 0.078 |
| dates:time_scalar | **0.616** | 0.640 |
| strings:dumps/escaped_values/object | **31.601** | 33.095 |
| dates:uuid_scalar_control | **0.652** | 0.678 |
| public:dumps:tree-pretty | **35.824** | 37.470 |
| frontend:dumps_root_empty | **0.139** | 0.146 |
| dates:date_scalar | **0.600** | 0.629 |
| numbers:loads_overflow_integers | **909.976** | 952.356 |
| output:small | **0.373** | 0.391 |
| dates:datetime_naive_scalar | **0.622** | 0.650 |
| output:integers_wide_unsigned | **198.969** | 209.919 |
| strings:loads/short_escaped/bytes | **0.130** | 0.136 |
| frontend:dumps_root_dense_escapes | **83.898** | 87.563 |

### jsonmodem baseline against jsonmodem baseline rebuild

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline rebuild | jsonmodem baseline |
| --- | ---: | ---: |
| output:dataclass_nested | **527.097** | 577.172 |
| output:dataclass_sorted | **575.475** | 626.412 |
| output:strings | **22.469** | 23.494 |
| public:loads:marine_ik | **14,393.200** | 14,904.480 |
| public:loads:apache_builds | **298.005** | 309.763 |

### jsonmodem earlier changes against jsonmodem baseline rebuild

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline rebuild | jsonmodem earlier changes |
| --- | ---: | ---: |
| strings:dumps/unicode_escapes/object | **22.174** | 28.451 |
| output:integer_keys | **36.394** | 38.865 |
| frontend:dumps_root_at_threshold | **0.146** | 0.157 |
| numbers:loads_zero_forms | **0.314** | 0.338 |
| strings:dumps/escaped_values/object | **31.745** | 33.309 |
| frontend:dumps_root_empty | **0.141** | 0.150 |
| dates:datetime_fixed_offset_16 | **2.326** | 2.441 |
| frontend:loads_root_late_quote | **18.711** | 19.750 |
| frontend:dumps_root_tiny | **0.152** | 0.159 |
| numbers:dumps_small | **0.167** | 0.174 |
| dates:datetime_fixed_offset_1024 | **92.612** | 96.380 |
| frontend:loads_long_string_array_view | **20.859** | 21.588 |

### jsonmodem selected changes against jsonmodem baseline rebuild

Microseconds per complete call; **lower is better**.

| Case | jsonmodem baseline rebuild | jsonmodem selected changes |
| --- | ---: | ---: |
| frontend:dumps_root_bmp | **11.700** | 93.220 |
| frontend:dumps_root_latin1 | **11.752** | 82.772 |
| frontend:dumps_root_non_bmp | **12.013** | 83.231 |
| public:dumps:poet | **1,917.412** | 4,448.267 |
| strings:dumps/unicode_escapes/object | **22.174** | 39.837 |
| public:dumps:twitter | **588.824** | 710.232 |
| public:dumps:twitterescaped | **593.918** | 726.076 |
| output:escaped | **89.002** | 106.459 |
| public:dumps:random | **843.843** | 989.905 |
| frontend:loads_small | **0.553** | 0.646 |
| frontend:loads_small_bytearray | **0.588** | 0.660 |
| strings:dumps/escaped_keys/object | **91.670** | 103.673 |
| frontend:loads_small_array_view | **0.666** | 0.738 |
| frontend:loads_small_memoryview | **0.666** | 0.740 |
| numbers:loads_small | **0.304** | 0.336 |
| frontend:dumps_root_at_threshold | **0.146** | 0.160 |
| dates:dict_control | **0.269** | 0.297 |
| numbers:loads_zero_forms | **0.314** | 0.345 |
| public:dumps:semanticscholar-corpus | **9,138.147** | 9,950.903 |
| output:integer_keys | **36.394** | 39.406 |
| numbers:loads_tiny_integers | **0.200** | 0.218 |
| public:dumps:apache_builds | **116.755** | 122.033 |
| public:dumps:tree-pretty | **35.653** | 37.470 |
| strings:dumps/escaped_values/object | **31.745** | 33.095 |
| output:small | **0.373** | 0.391 |
| numbers:dumps_wide_unsigned | **201.690** | 211.993 |
| numpy:datetime_Y_4096 | **71.974** | 75.674 |
| numbers:loads_long_fractions | **728.162** | 758.453 |
| numbers:loads_overflow_integers | **911.661** | 952.356 |
| dates:uuid_scalar_control | **0.657** | 0.678 |
| frontend:dumps_root_empty | **0.141** | 0.146 |
| dates:time_scalar | **0.618** | 0.640 |
| public:dumps:instruments | **221.341** | 228.184 |
| dates:date_scalar | **0.609** | 0.629 |
| strings:loads/short_plain/bytes | **0.093** | 0.096 |

## Limits

Results apply to these cases and recorded library/interpreter versions. A favorable mean does not establish a universal advantage or memory-safety equivalence. This export contains no RSS, allocation or streaming measurements; those require separate exports.
