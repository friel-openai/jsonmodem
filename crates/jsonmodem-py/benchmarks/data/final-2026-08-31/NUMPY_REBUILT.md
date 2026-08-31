# NumPy: rebuilt control

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

Complete dumps latency (us). Lower is better.

| Case | Rebuilt | Final | orjson (rebuilt runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 3.592 | 3.512 | **1.904** | 1.923 |
| `datetime_D_4096` | 107.080 | **107.043** | 265.002 | 268.246 |
| `datetime_D_scalar` | 3.141 | 3.047 | 0.872 | **0.866** |
| `datetime_M_16` | 3.509 | 3.434 | **1.950** | 1.976 |
| `datetime_M_4096` | 80.395 | **80.382** | 278.174 | 281.030 |
| `datetime_M_scalar` | 3.108 | 3.041 | **0.869** | 0.877 |
| `datetime_Y_16` | 3.459 | 3.378 | **1.905** | 1.924 |
| `datetime_Y_4096` | 70.941 | **70.796** | 264.567 | 267.455 |
| `datetime_Y_scalar` | 3.147 | 3.061 | **0.867** | 0.872 |
| `datetime_ns_16` | 3.669 | 3.639 | **2.023** | 2.028 |
| `datetime_ns_4096` | **127.228** | 128.562 | 292.221 | 295.607 |
| `datetime_ns_scalar` | 3.220 | 3.174 | **0.914** | 0.931 |
| `datetime_s_16` | 3.588 | 3.509 | **1.922** | 1.935 |
| `datetime_s_4096` | 102.892 | **101.016** | 273.194 | 274.796 |
| `datetime_s_scalar` | 3.138 | 3.036 | 0.867 | **0.866** |
| `datetime_us_16` | 3.654 | 3.557 | **2.019** | 2.024 |
| `datetime_us_4096` | **112.183** | 112.287 | 293.703 | 296.492 |
| `datetime_us_4096_naive_utc` | 120.868 | **118.574** | 264.796 | 264.588 |
| `datetime_us_4096_naive_utc_omit_microseconds` | **102.066** | 102.345 | 277.206 | 278.609 |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | **99.832** | 100.160 | 265.802 | 268.528 |
| `datetime_us_4096_naive_utc_z` | 116.336 | **115.997** | 294.230 | 296.610 |
| `datetime_us_4096_omit_microseconds` | **98.440** | 98.992 | 270.479 | 273.418 |
| `datetime_us_4096_omit_microseconds_utc_z` | **99.206** | 99.246 | 270.525 | 270.598 |
| `datetime_us_4096_utc_z` | **112.259** | 112.539 | 294.071 | 294.242 |
| `datetime_us_empty` | 3.015 | 2.931 | 0.878 | **0.877** |
| `datetime_us_matrix` | **112.560** | 113.848 | 295.962 | 298.710 |
| `datetime_us_scalar` | 3.219 | 3.150 | **0.906** | 0.913 |
| `datetime_us_under_dict` | 120.232 | **119.067** | 294.816 | 294.277 |
