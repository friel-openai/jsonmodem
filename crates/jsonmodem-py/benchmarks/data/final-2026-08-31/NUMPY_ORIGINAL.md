# NumPy: original control

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

Complete dumps latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 3.546 | 3.541 | **1.911** | 1.914 |
| `datetime_D_4096` | 106.952 | **106.927** | 265.960 | 268.419 |
| `datetime_D_scalar` | 3.109 | 3.083 | 0.882 | **0.869** |
| `datetime_M_16` | 3.468 | 3.462 | **1.963** | 1.970 |
| `datetime_M_4096` | **80.334** | 81.075 | 278.385 | 280.762 |
| `datetime_M_scalar` | 3.094 | 3.083 | 0.882 | **0.872** |
| `datetime_Y_16` | 3.422 | 3.423 | **1.920** | 1.925 |
| `datetime_Y_4096` | **70.788** | 71.377 | 264.859 | 267.095 |
| `datetime_Y_scalar` | 3.114 | 3.110 | **0.879** | 0.883 |
| `datetime_ns_16` | 3.671 | 3.660 | 2.034 | **2.030** |
| `datetime_ns_4096` | 128.057 | **127.904** | 292.031 | 294.257 |
| `datetime_ns_scalar` | 3.185 | 3.167 | 0.924 | **0.920** |
| `datetime_s_16` | 3.533 | 3.531 | **1.930** | 1.940 |
| `datetime_s_4096` | 103.033 | **100.858** | 273.271 | 275.031 |
| `datetime_s_scalar` | 3.095 | 3.079 | 0.878 | **0.868** |
| `datetime_us_16` | 3.603 | 3.603 | 2.037 | **2.031** |
| `datetime_us_4096` | 112.600 | **112.154** | 293.613 | 295.798 |
| `datetime_us_4096_naive_utc` | 121.057 | **118.684** | 263.284 | 264.730 |
| `datetime_us_4096_naive_utc_omit_microseconds` | **102.642** | 102.699 | 277.539 | 277.405 |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 100.648 | **100.369** | 265.611 | 268.600 |
| `datetime_us_4096_naive_utc_z` | 116.352 | **115.133** | 293.946 | 296.604 |
| `datetime_us_4096_omit_microseconds` | **98.953** | 99.407 | 269.815 | 274.121 |
| `datetime_us_4096_omit_microseconds_utc_z` | 99.739 | **99.543** | 270.880 | 271.645 |
| `datetime_us_4096_utc_z` | 113.312 | **112.839** | 293.208 | 294.043 |
| `datetime_us_empty` | 2.952 | 2.945 | **0.877** | 0.880 |
| `datetime_us_matrix` | 113.917 | **113.083** | 296.625 | 299.069 |
| `datetime_us_scalar` | 3.196 | 3.180 | 0.917 | **0.915** |
| `datetime_us_under_dict` | 121.469 | **119.341** | 293.910 | 294.638 |
