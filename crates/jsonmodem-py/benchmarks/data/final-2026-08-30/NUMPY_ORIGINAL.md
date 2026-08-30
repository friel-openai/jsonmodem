# NumPy datetime64: original control

Original is the existing PR #3 build (`b7fe329`).
Final is the changed implementation (`b0f3190`).
The reference is orjson 3.11.9. See [definitions and methods](README.md).

[Summary](PERFORMANCE_FINAL.md). Latencies are microseconds per complete call.
Each process measures one jsonmodem build and orjson. The two orjson columns come from different processes.
Values are rounded; bold uses unrounded minima.

Complete dumps latency (us). Lower is better.

| Case | Original | Final | orjson (original runs) | orjson (final runs) |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 6.217 | 3.548 | 1.924 | **1.894** |
| `datetime_D_4096` | 766.148 | **107.825** | 267.985 | 268.388 |
| `datetime_D_scalar` | 3.388 | 3.081 | 0.879 | **0.868** |
| `datetime_M_16` | 6.098 | 3.470 | 1.973 | **1.955** |
| `datetime_M_4096` | 735.977 | **81.099** | 280.462 | 280.828 |
| `datetime_M_scalar` | 3.384 | 3.073 | **0.870** | 0.878 |
| `datetime_Y_16` | 6.004 | 3.410 | 1.954 | **1.909** |
| `datetime_Y_4096` | 720.567 | **71.750** | 266.933 | 267.019 |
| `datetime_Y_scalar` | 3.423 | 3.120 | **0.881** | 0.891 |
| `datetime_ns_16` | 6.581 | 3.659 | 2.031 | **2.008** |
| `datetime_ns_4096` | 844.931 | **128.696** | 293.603 | 294.748 |
| `datetime_ns_scalar` | 3.471 | 3.153 | 0.921 | **0.910** |
| `datetime_s_16` | 6.009 | 3.515 | 1.951 | **1.923** |
| `datetime_s_4096` | 712.830 | **103.957** | 274.073 | 275.134 |
| `datetime_s_scalar` | 3.382 | 3.076 | 0.875 | **0.867** |
| `datetime_us_16` | 6.527 | 3.610 | 2.033 | **2.018** |
| `datetime_us_4096` | 827.410 | **114.036** | 295.460 | 296.442 |
| `datetime_us_4096_naive_utc` | 841.122 | **122.194** | 262.859 | 266.313 |
| `datetime_us_4096_naive_utc_omit_microseconds` | 718.727 | **102.407** | 277.328 | 278.255 |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 717.557 | **101.351** | 267.752 | 269.715 |
| `datetime_us_4096_naive_utc_z` | 837.926 | **117.723** | 294.789 | 296.647 |
| `datetime_us_4096_omit_microseconds` | 707.012 | **99.969** | 273.255 | 272.254 |
| `datetime_us_4096_omit_microseconds_utc_z` | 706.307 | **100.191** | 271.280 | 271.296 |
| `datetime_us_4096_utc_z` | 829.573 | **114.438** | 293.416 | 294.576 |
| `datetime_us_empty` | 2.948 | 2.962 | **0.873** | 0.878 |
| `datetime_us_matrix` | 829.197 | **114.909** | 298.481 | 300.567 |
| `datetime_us_scalar` | 3.495 | 3.145 | 0.922 | **0.906** |
| `datetime_us_under_dict` | 835.219 | **123.091** | 294.643 | 294.928 |
