# NumPy serialization: 64 fixed cases

The 7b control is jsonmodem at `7b7e21c3bd49d22c0964c4a30be16b5367160caf`. The 7b rebuild compiles the same source again.
The 963 corrected build is jsonmodem at `96318df6102bf40e30383125f77fa300ca236047`.
It combines decimal parsing, checked Unicode conversion, tuple initialization, and the NumPy container writer.
These measurements do not isolate the writer's effect.

Each of five measurement groups ran all three builds in separate processes, with paired orjson in each process.
Every process measured all 64 cases, taking three samples per library per case after calibration.
Calibration doubles the shared iteration count until the slower library's batch takes at least 40 milliseconds.
The numeric lists repeat one scalar object 1,024 times. The numeric dictionaries use one scalar object for 128 distinct keys.
They do not measure varied values or freshly created containers on every call.

The parent process also reaped one additional child that exited successfully. Its executable and lifetime were not recorded, so whether it overlapped measurement is unknown.
The timing-rule result describes these measurements; it does not establish complete process attribution.

All tables round times to three decimal places. Bold uses the unrounded times,
so equal displayed values may have different highlighting.

## Geometric means

Lower is better. Times are microseconds (us) per complete `dumps` call; the best measured time in each row is bold.
Each case has equal weight. Each entry is the median of five case geometric means, one per process.
The paired orjson column uses the reference measurements from that build's processes.
These are NumPy-suite geometric means, not the overall 275-case benchmark result.

| Cases | Build | jsonmodem, us | Paired orjson, us |
| --- | --- | ---: | ---: |
| All 64 | 7b control | 16.011 | **7.749** |
| All 64 | 7b rebuild | 16.191 | **7.803** |
| All 64 | 963 corrected | 12.334 | **7.783** |
| 12 numeric lists | 7b control | 149.055 | **28.694** |
| 12 numeric lists | 7b rebuild | 149.487 | **28.742** |
| 12 numeric lists | 963 corrected | 75.252 | **28.758** |

## Individual cases

Lower is better. Times are microseconds per complete `dumps` call; each row's minimum is bold.
Each jsonmodem entry is the median of five process medians. Each process median uses its three samples.
The orjson display column pools its 15 process medians. That pooled value is not used in the timing decision.

| Case | 7b control, us | 7b rebuild, us | 963 corrected, us | orjson, us |
| --- | ---: | ---: | ---: | ---: |
| datetime_Y_scalar | 2.829 | 2.806 | 2.804 | **0.886** |
| datetime_Y_16 | 3.502 | 3.586 | 3.502 | **1.927** |
| datetime_Y_4096 | 75.057 | **75.024** | 76.346 | 264.854 |
| datetime_M_scalar | 2.813 | 2.782 | 2.809 | **0.878** |
| datetime_M_16 | 3.508 | 3.591 | 3.516 | **1.960** |
| datetime_M_4096 | **82.118** | 83.062 | 83.724 | 280.169 |
| datetime_D_scalar | 2.782 | 2.801 | 2.788 | **0.889** |
| datetime_D_16 | 3.577 | 3.698 | 3.566 | **1.918** |
| datetime_D_4096 | 105.179 | 106.377 | **104.945** | 267.523 |
| datetime_s_scalar | 2.773 | 2.773 | 2.765 | **0.875** |
| datetime_s_16 | 3.432 | 3.545 | 3.427 | **1.937** |
| datetime_s_4096 | **70.352** | 71.328 | 71.003 | 274.643 |
| datetime_us_scalar | 2.825 | 2.881 | 2.817 | **0.901** |
| datetime_us_16 | 3.503 | 3.569 | 3.476 | **2.021** |
| datetime_us_4096 | **75.398** | 76.775 | 78.177 | 295.775 |
| datetime_ns_scalar | 2.826 | 2.896 | 2.817 | **0.905** |
| datetime_ns_16 | 3.503 | 3.582 | 3.518 | **2.024** |
| datetime_ns_4096 | 81.665 | **80.304** | 80.367 | 294.273 |
| datetime_us_4096_naive_utc | **83.941** | 83.980 | 84.120 | 263.017 |
| datetime_us_4096_omit_microseconds | **71.176** | 71.370 | 72.494 | 272.464 |
| datetime_us_4096_utc_z | 77.602 | 77.589 | **76.736** | 293.871 |
| datetime_us_4096_naive_utc_omit_microseconds | 72.177 | 72.440 | **71.580** | 277.991 |
| datetime_us_4096_naive_utc_z | 77.988 | **77.877** | 80.511 | 295.614 |
| datetime_us_4096_omit_microseconds_utc_z | **71.461** | 72.171 | 73.975 | 271.158 |
| datetime_us_4096_naive_utc_omit_microseconds_utc_z | **74.237** | 74.963 | 74.379 | 268.868 |
| datetime_us_empty | 3.022 | 3.049 | 2.972 | **0.868** |
| datetime_us_matrix | 77.978 | 77.382 | **77.167** | 298.107 |
| datetime_us_under_dict | 80.853 | **79.453** | 81.027 | 293.970 |
| numeric_bool_scalar | 0.889 | 0.856 | 0.866 | **0.250** |
| numeric_int8_scalar | 0.872 | 0.873 | 0.871 | **0.253** |
| numeric_int16_scalar | 0.875 | 0.875 | 0.873 | **0.256** |
| numeric_int32_scalar | 0.870 | 0.876 | 0.877 | **0.257** |
| numeric_int64_scalar | 0.907 | 0.884 | 0.887 | **0.271** |
| numeric_uint8_scalar | 0.879 | 0.891 | 0.879 | **0.252** |
| numeric_uint16_scalar | 0.892 | 0.900 | 0.880 | **0.258** |
| numeric_uint32_scalar | 0.895 | 0.897 | 0.890 | **0.253** |
| numeric_uint64_scalar | 0.900 | 0.907 | 0.892 | **0.274** |
| numeric_float16_scalar | 0.918 | 0.915 | 0.910 | **0.274** |
| numeric_float32_scalar | 0.917 | 0.903 | 0.909 | **0.271** |
| numeric_float64_scalar | 0.909 | 0.916 | 0.906 | **0.269** |
| numeric_bool_list1024 | 135.898 | 139.990 | 49.219 | **23.272** |
| numeric_bool_dict128 | 22.542 | 22.749 | 8.917 | **4.176** |
| numeric_int8_list1024 | 138.030 | 140.822 | 58.435 | **22.410** |
| numeric_int8_dict128 | 23.333 | 23.424 | 9.905 | **4.040** |
| numeric_int16_list1024 | 138.925 | 141.641 | 70.906 | **22.770** |
| numeric_int16_dict128 | 23.377 | 23.606 | 11.445 | **4.180** |
| numeric_int32_list1024 | 140.694 | 143.808 | 74.485 | **24.472** |
| numeric_int32_dict128 | 23.858 | 24.335 | 11.868 | **4.442** |
| numeric_int64_list1024 | 145.001 | 146.466 | 80.342 | **28.296** |
| numeric_int64_dict128 | 24.882 | 25.269 | 12.405 | **5.054** |
| numeric_uint8_list1024 | 142.297 | 145.438 | 63.237 | **22.565** |
| numeric_uint8_dict128 | 23.698 | 23.905 | 10.368 | **4.101** |
| numeric_uint16_list1024 | 145.214 | 145.996 | 72.441 | **22.975** |
| numeric_uint16_dict128 | 23.923 | 24.129 | 11.652 | **4.245** |
| numeric_uint32_list1024 | 146.060 | 149.974 | 74.953 | **24.495** |
| numeric_uint32_dict128 | 24.387 | 24.368 | 12.074 | **4.441** |
| numeric_uint64_list1024 | 149.083 | 152.108 | 79.950 | **29.276** |
| numeric_uint64_dict128 | 25.350 | 25.665 | 12.725 | **5.136** |
| numeric_float16_list1024 | 163.718 | 164.563 | 96.251 | **47.505** |
| numeric_float16_dict128 | 27.557 | 26.897 | 15.193 | **7.150** |
| numeric_float32_list1024 | 167.125 | 165.287 | 94.107 | **46.036** |
| numeric_float32_dict128 | 26.740 | 26.910 | 14.845 | **6.962** |
| numeric_float64_list1024 | 170.930 | 173.359 | 107.628 | **49.121** |
| numeric_float64_dict128 | 27.318 | 28.105 | 16.237 | **7.518** |

## Timing decision and regressions

The registered rule requires at least a 5% median improvement across the 12 list cases against both controls,
with any improvement in at least four of five groups. A non-list case rejects the timing rule when it is
more than 3% slower by median and more than 3% slower in at least four groups.
Individual list losses remain visible even though the list decision uses the group's geometric mean.

The registered timing rule passed: **yes**.
A timing-rule pass is not integration approval.

- Against 7b control: 5 of five list groups improved; non-list rejections: none.
- Against 7b rebuild: 5 of five list groups improved; non-list rejections: none.

The table below includes every case with a median corrected/control time ratio above one.
Lower time is better. Times are absolute microseconds; the smaller time in each row is bold.
Group counts use paired process comparisons, which can differ from comparing the displayed medians.

| Case | Control | Control, us | Corrected, us | Slower groups | Groups over 3% slower | Rejects rule |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| datetime_Y_16 | 7b control | 3.502 | **3.502** | 3/5 | 1/5 | no |
| datetime_Y_4096 | 7b control | **75.057** | 76.346 | 5/5 | 1/5 | no |
| datetime_M_16 | 7b control | **3.508** | 3.516 | 3/5 | 1/5 | no |
| datetime_M_4096 | 7b control | **82.118** | 83.724 | 5/5 | 0/5 | no |
| datetime_D_scalar | 7b control | **2.782** | 2.788 | 3/5 | 0/5 | no |
| datetime_D_16 | 7b control | 3.577 | **3.566** | 3/5 | 0/5 | no |
| datetime_s_16 | 7b control | 3.432 | **3.427** | 3/5 | 0/5 | no |
| datetime_s_4096 | 7b control | **70.352** | 71.003 | 4/5 | 1/5 | no |
| datetime_us_4096 | 7b control | **75.398** | 78.177 | 3/5 | 2/5 | no |
| datetime_ns_16 | 7b control | **3.503** | 3.518 | 3/5 | 0/5 | no |
| datetime_ns_4096 | 7b control | 81.665 | **80.367** | 3/5 | 1/5 | no |
| datetime_us_4096_naive_utc | 7b control | **83.941** | 84.120 | 3/5 | 1/5 | no |
| datetime_us_4096_omit_microseconds | 7b control | **71.176** | 72.494 | 3/5 | 1/5 | no |
| datetime_us_4096_naive_utc_z | 7b control | **77.988** | 80.511 | 4/5 | 3/5 | no |
| datetime_us_4096_omit_microseconds_utc_z | 7b control | **71.461** | 73.975 | 4/5 | 3/5 | no |
| datetime_us_4096_naive_utc_omit_microseconds_utc_z | 7b control | **74.237** | 74.379 | 3/5 | 0/5 | no |
| datetime_us_under_dict | 7b control | **80.853** | 81.027 | 3/5 | 1/5 | no |
| numeric_int16_scalar | 7b control | 0.875 | **0.873** | 4/5 | 0/5 | no |
| numeric_float32_scalar | 7b control | 0.917 | **0.909** | 3/5 | 0/5 | no |
| numeric_float64_scalar | 7b control | 0.909 | **0.906** | 3/5 | 0/5 | no |
| datetime_Y_4096 | 7b rebuild | **75.024** | 76.346 | 3/5 | 2/5 | no |
| datetime_M_scalar | 7b rebuild | **2.782** | 2.809 | 3/5 | 2/5 | no |
| datetime_M_4096 | 7b rebuild | **83.062** | 83.724 | 3/5 | 1/5 | no |
| datetime_s_scalar | 7b rebuild | 2.773 | **2.765** | 3/5 | 0/5 | no |
| datetime_us_4096 | 7b rebuild | **76.775** | 78.177 | 3/5 | 1/5 | no |
| datetime_ns_4096 | 7b rebuild | **80.304** | 80.367 | 4/5 | 2/5 | no |
| datetime_us_4096_naive_utc | 7b rebuild | **83.980** | 84.120 | 3/5 | 0/5 | no |
| datetime_us_4096_omit_microseconds | 7b rebuild | **71.370** | 72.494 | 3/5 | 1/5 | no |
| datetime_us_4096_utc_z | 7b rebuild | 77.589 | **76.736** | 3/5 | 2/5 | no |
| datetime_us_4096_naive_utc_z | 7b rebuild | **77.877** | 80.511 | 4/5 | 2/5 | no |
| datetime_us_4096_omit_microseconds_utc_z | 7b rebuild | **72.171** | 73.975 | 4/5 | 2/5 | no |
| datetime_us_matrix | 7b rebuild | 77.382 | **77.167** | 3/5 | 0/5 | no |
| datetime_us_under_dict | 7b rebuild | **79.453** | 81.027 | 3/5 | 2/5 | no |
| numeric_bool_scalar | 7b rebuild | **0.856** | 0.866 | 5/5 | 0/5 | no |
| numeric_int32_scalar | 7b rebuild | **0.876** | 0.877 | 3/5 | 0/5 | no |
| numeric_int64_scalar | 7b rebuild | **0.884** | 0.887 | 4/5 | 0/5 | no |
| numeric_float32_scalar | 7b rebuild | **0.903** | 0.909 | 3/5 | 0/5 | no |

[numpy.json](numpy.json) retains all 15 workers, all 5,760 library samples, input signatures, runtime hashes,
paired reference measurements, five-group summaries, and every per-case loss.
Memory use, cold initialization, and other interpreters are separate measurements.
