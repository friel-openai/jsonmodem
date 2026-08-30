# NumPy datetime64: rebuilt control

Rebuilt is a new compilation of unchanged PR #3 source (`b7fe329`).
Final is the changed implementation (`b0f3190`).
The reference is orjson 3.11.9. See [definitions and methods](README.md).

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

Complete dumps latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 6.221 | 3.547 | 1.913 | **1.899** |
| `datetime_D_4096` | 760.873 | **107.960** | 267.824 | 268.231 |
| `datetime_D_scalar` | 3.392 | 3.068 | 0.878 | **0.867** |
| `datetime_M_16` | 6.097 | 3.448 | 1.960 | **1.956** |
| `datetime_M_4096` | 732.640 | **82.602** | 280.444 | 280.861 |
| `datetime_M_scalar` | 3.345 | 3.089 | 0.880 | **0.870** |
| `datetime_Y_16` | 6.038 | 3.390 | **1.911** | 1.913 |
| `datetime_Y_4096` | 717.153 | **72.336** | 266.720 | 267.097 |
| `datetime_Y_scalar` | 3.358 | 3.070 | **0.872** | 0.891 |
| `datetime_ns_16` | 6.613 | 3.637 | 2.016 | **2.015** |
| `datetime_ns_4096` | 844.946 | **129.070** | 294.003 | 294.413 |
| `datetime_ns_scalar` | 3.459 | 3.163 | 0.918 | **0.914** |
| `datetime_s_16` | 6.101 | 3.524 | 1.936 | **1.918** |
| `datetime_s_4096` | 711.641 | **104.469** | 275.298 | 274.813 |
| `datetime_s_scalar` | 3.378 | 3.081 | 0.882 | **0.873** |
| `datetime_us_16` | 6.537 | 3.588 | 2.029 | **2.009** |
| `datetime_us_4096` | 831.836 | **113.538** | 295.533 | 297.897 |
| `datetime_us_4096_naive_utc` | 839.172 | **122.564** | 262.377 | 264.419 |
| `datetime_us_4096_naive_utc_omit_microseconds` | 717.358 | **103.008** | 279.003 | 277.710 |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 718.273 | **101.755** | 267.828 | 268.957 |
| `datetime_us_4096_naive_utc_z` | 835.002 | **117.865** | 295.603 | 297.447 |
| `datetime_us_4096_omit_microseconds` | 708.351 | **99.707** | 273.592 | 272.484 |
| `datetime_us_4096_omit_microseconds_utc_z` | 705.072 | **100.864** | 270.651 | 271.661 |
| `datetime_us_4096_utc_z` | 829.856 | **113.453** | 293.074 | 294.505 |
| `datetime_us_empty` | 2.949 | 2.946 | 0.881 | **0.873** |
| `datetime_us_matrix` | 825.465 | **114.588** | 298.226 | 299.663 |
| `datetime_us_scalar` | 3.459 | 3.142 | 0.915 | **0.904** |
| `datetime_us_under_dict` | 832.155 | **123.001** | 293.999 | 294.126 |
