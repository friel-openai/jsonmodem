# NumPy memory

[Summary](PERFORMANCE_FINAL.md). Medians of three process observations.
Memray uses one tracked call after ten warmups.
Peak live bytes are Memray's reported capture peak, not process RSS or a separate reconstruction.
RSS uses ten calls without warmup. Peak RSS is Linux VmHWM, including preparation; it is not ru_maxrss.
Four libraries and three repetitions do not fully balance execution positions. There is no memory mean.

Allocation requests (requests). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 47 | 47 | 47 | **40** |
| `datetime_D_4096` | **48** | **48** | **48** | 4,127 |
| `datetime_D_scalar` | 49 | 49 | 49 | **22** |
| `datetime_M_16` | 47 | 47 | 47 | **40** |
| `datetime_M_4096` | **48** | **48** | **48** | 4,127 |
| `datetime_M_scalar` | 49 | 49 | 49 | **22** |
| `datetime_Y_16` | 47 | 47 | 47 | **40** |
| `datetime_Y_4096` | **48** | **48** | **48** | 4,127 |
| `datetime_Y_scalar` | 49 | 49 | 49 | **22** |
| `datetime_ns_16` | 48 | 48 | 48 | **41** |
| `datetime_ns_4096` | **49** | **49** | **49** | 4,128 |
| `datetime_ns_scalar` | 50 | 50 | 50 | **23** |
| `datetime_s_16` | 47 | 47 | 47 | **40** |
| `datetime_s_4096` | **48** | **48** | **48** | 4,127 |
| `datetime_s_scalar` | 49 | 49 | 49 | **22** |
| `datetime_us_16` | 48 | 48 | 48 | **41** |
| `datetime_us_4096` | **49** | **49** | **49** | 4,128 |
| `datetime_us_4096_naive_utc` | **50** | **50** | **50** | 4,129 |
| `datetime_us_4096_naive_utc_omit_microseconds` | **49** | **49** | **49** | 4,128 |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | **49** | **49** | **49** | 4,128 |
| `datetime_us_4096_naive_utc_z` | **49** | **49** | **49** | 4,128 |
| `datetime_us_4096_omit_microseconds` | **49** | **49** | **49** | 4,128 |
| `datetime_us_4096_omit_microseconds_utc_z` | **49** | **49** | **49** | 4,128 |
| `datetime_us_4096_utc_z` | **49** | **49** | **49** | 4,128 |
| `datetime_us_empty` | 45 | 45 | 45 | **25** |
| `datetime_us_matrix` | **49** | **49** | **49** | 4,197 |
| `datetime_us_scalar` | 50 | 50 | 50 | **23** |
| `datetime_us_under_dict` | **52** | **52** | **52** | 4,128 |

Total allocated bytes (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 4.570 | 4.570 | 4.570 | **2.926** |
| `datetime_D_4096` | 347.258 | 347.258 | 347.258 | **332.854** |
| `datetime_D_scalar` | 3.714 | 3.714 | 3.714 | **2.601** |
| `datetime_M_16` | 4.570 | 4.570 | 4.570 | **2.926** |
| `datetime_M_4096` | 347.258 | 347.258 | 347.258 | **332.854** |
| `datetime_M_scalar` | 3.714 | 3.714 | 3.714 | **2.601** |
| `datetime_Y_16` | 4.570 | 4.570 | 4.570 | **2.926** |
| `datetime_Y_4096` | 347.258 | 347.258 | 347.258 | **332.854** |
| `datetime_Y_scalar` | 3.714 | 3.714 | 3.714 | **2.601** |
| `datetime_ns_16` | 4.722 | 4.722 | 4.722 | **3.079** |
| `datetime_ns_4096` | 375.300 | 375.300 | 375.300 | **360.898** |
| `datetime_ns_scalar` | 3.770 | 3.770 | 3.770 | **2.651** |
| `datetime_s_16` | 4.570 | 4.570 | 4.570 | **2.926** |
| `datetime_s_4096` | 347.258 | 347.258 | 347.258 | **332.854** |
| `datetime_s_scalar` | 3.714 | 3.714 | 3.714 | **2.601** |
| `datetime_us_16` | 4.722 | 4.722 | 4.722 | **3.079** |
| `datetime_us_4096` | 375.300 | 375.300 | 375.300 | **360.898** |
| `datetime_us_4096_naive_utc` | 655.300 | 655.300 | 655.300 | **640.931** |
| `datetime_us_4096_naive_utc_omit_microseconds` | 371.300 | 371.300 | 371.300 | **356.898** |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 351.300 | 351.300 | 351.300 | **336.898** |
| `datetime_us_4096_naive_utc_z` | 379.300 | 379.300 | 379.300 | **364.898** |
| `datetime_us_4096_omit_microseconds` | 347.300 | 347.300 | 347.300 | **332.898** |
| `datetime_us_4096_omit_microseconds_utc_z` | 347.300 | 347.300 | 347.300 | **332.898** |
| `datetime_us_4096_utc_z` | 375.300 | 375.300 | 375.300 | **360.898** |
| `datetime_us_empty` | 3.245 | 3.245 | 3.245 | **2.673** |
| `datetime_us_matrix` | 375.433 | 375.433 | 375.433 | **371.688** |
| `datetime_us_scalar` | 3.770 | 3.770 | 3.770 | **2.651** |
| `datetime_us_under_dict` | 839.372 | 839.372 | 839.372 | **360.898** |

Peak live bytes tracked by Memray (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 2.776 | 2.776 | 2.776 | **2.053** |
| `datetime_D_4096` | 249.839 | 249.839 | 249.839 | **128.973** |
| `datetime_D_scalar` | 2.298 | 2.298 | 2.298 | **2.092** |
| `datetime_M_16` | 2.776 | 2.776 | 2.776 | **2.053** |
| `datetime_M_4096` | 249.839 | 249.839 | 249.839 | **128.973** |
| `datetime_M_scalar` | 2.298 | 2.298 | 2.298 | **2.092** |
| `datetime_Y_16` | 2.776 | 2.776 | 2.776 | **2.053** |
| `datetime_Y_4096` | 249.839 | 249.839 | 249.839 | **128.973** |
| `datetime_Y_scalar` | 2.298 | 2.298 | 2.298 | **2.092** |
| `datetime_ns_16` | 2.928 | 2.928 | 2.928 | **2.095** |
| `datetime_ns_4096` | 277.881 | 277.881 | 277.881 | **128.979** |
| `datetime_ns_scalar` | 2.340 | 2.340 | 2.340 | **2.134** |
| `datetime_s_16` | 2.776 | 2.776 | 2.776 | **2.053** |
| `datetime_s_4096` | 249.839 | 249.839 | 249.839 | **128.973** |
| `datetime_s_scalar` | 2.298 | 2.298 | 2.298 | **2.092** |
| `datetime_us_16` | 2.928 | 2.928 | 2.928 | **2.095** |
| `datetime_us_4096` | 277.881 | 277.881 | 277.881 | **128.979** |
| `datetime_us_4096_naive_utc` | 429.881 | 429.881 | 429.881 | **256.985** |
| `datetime_us_4096_naive_utc_omit_microseconds` | 273.881 | 273.881 | 273.881 | **128.979** |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 253.881 | 253.881 | 253.881 | **128.974** |
| `datetime_us_4096_naive_utc_z` | 281.881 | 281.881 | 281.881 | **128.980** |
| `datetime_us_4096_omit_microseconds` | 249.881 | 249.881 | 249.881 | **128.973** |
| `datetime_us_4096_omit_microseconds_utc_z` | 249.881 | 249.881 | 249.881 | **128.973** |
| `datetime_us_4096_utc_z` | 277.881 | 277.881 | 277.881 | **128.979** |
| `datetime_us_empty` | **1.878** | **1.878** | **1.878** | 2.095 |
| `datetime_us_matrix` | 277.982 | 277.982 | 277.982 | **134.925** |
| `datetime_us_scalar` | 2.340 | 2.340 | 2.340 | **2.134** |
| `datetime_us_under_dict` | 349.031 | 349.031 | 349.031 | **128.979** |

Peak RSS, including preparation (Linux VmHWM) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 40.695 | 40.801 | 40.586 | **39.719** |
| `datetime_D_4096` | 40.711 | 40.723 | 40.711 | **39.773** |
| `datetime_D_scalar` | 40.625 | 40.660 | 40.535 | **39.715** |
| `datetime_M_16` | 40.625 | 40.797 | 40.586 | **39.852** |
| `datetime_M_4096` | 40.680 | 40.602 | 40.656 | **39.840** |
| `datetime_M_scalar` | 40.617 | 40.617 | 40.590 | **39.754** |
| `datetime_Y_16` | 40.605 | 40.672 | 40.594 | **39.766** |
| `datetime_Y_4096` | 40.590 | 40.664 | 40.734 | **39.832** |
| `datetime_Y_scalar` | 40.691 | 40.602 | 40.582 | **39.883** |
| `datetime_ns_16` | 40.629 | 40.586 | 40.664 | **39.770** |
| `datetime_ns_4096` | 40.660 | 40.590 | 41.141 | **39.844** |
| `datetime_ns_scalar` | 40.754 | 40.574 | 40.531 | **39.852** |
| `datetime_s_16` | 40.703 | 40.695 | 40.676 | **39.762** |
| `datetime_s_4096` | 40.668 | 40.715 | 40.598 | **39.719** |
| `datetime_s_scalar` | 40.703 | 40.617 | 40.578 | **39.844** |
| `datetime_us_16` | 40.699 | 40.695 | 40.547 | **39.777** |
| `datetime_us_4096` | 40.582 | 40.688 | 40.703 | **39.844** |
| `datetime_us_4096_naive_utc` | 41.152 | 41.152 | 41.008 | **39.727** |
| `datetime_us_4096_naive_utc_omit_microseconds` | 40.602 | 40.688 | 40.656 | **39.785** |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 40.648 | 40.645 | 40.551 | **39.801** |
| `datetime_us_4096_naive_utc_z` | 40.691 | 40.586 | 40.590 | **39.727** |
| `datetime_us_4096_omit_microseconds` | 40.672 | 40.699 | 40.555 | **39.801** |
| `datetime_us_4096_omit_microseconds_utc_z` | 40.703 | 40.691 | 40.711 | **39.816** |
| `datetime_us_4096_utc_z` | 40.750 | 40.625 | 40.637 | **39.773** |
| `datetime_us_empty` | 40.699 | 40.797 | 40.641 | **39.766** |
| `datetime_us_matrix` | 40.645 | 40.578 | 40.590 | **39.887** |
| `datetime_us_scalar` | 40.660 | 40.688 | 40.527 | **39.766** |
| `datetime_us_under_dict` | 40.676 | 40.594 | 41.117 | **39.723** |

Prepared RSS (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 40.695 | 40.801 | 40.586 | **39.719** |
| `datetime_D_4096` | 40.711 | 40.723 | 40.711 | **39.773** |
| `datetime_D_scalar` | 40.625 | 40.660 | 40.535 | **39.715** |
| `datetime_M_16` | 40.625 | 40.797 | 40.586 | **39.852** |
| `datetime_M_4096` | 40.680 | 40.602 | 40.656 | **39.840** |
| `datetime_M_scalar` | 40.617 | 40.617 | 40.590 | **39.754** |
| `datetime_Y_16` | 40.605 | 40.672 | 40.594 | **39.766** |
| `datetime_Y_4096` | 40.590 | 40.664 | 40.734 | **39.832** |
| `datetime_Y_scalar` | 40.691 | 40.602 | 40.582 | **39.883** |
| `datetime_ns_16` | 40.629 | 40.586 | 40.664 | **39.770** |
| `datetime_ns_4096` | 40.660 | 40.590 | 40.707 | **39.844** |
| `datetime_ns_scalar` | 40.754 | 40.574 | 40.531 | **39.852** |
| `datetime_s_16` | 40.703 | 40.695 | 40.676 | **39.762** |
| `datetime_s_4096` | 40.668 | 40.715 | 40.598 | **39.719** |
| `datetime_s_scalar` | 40.703 | 40.617 | 40.578 | **39.844** |
| `datetime_us_16` | 40.699 | 40.695 | 40.547 | **39.777** |
| `datetime_us_4096` | 40.582 | 40.688 | 40.703 | **39.844** |
| `datetime_us_4096_naive_utc` | 40.660 | 40.660 | 40.574 | **39.727** |
| `datetime_us_4096_naive_utc_omit_microseconds` | 40.602 | 40.688 | 40.656 | **39.785** |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 40.648 | 40.645 | 40.551 | **39.801** |
| `datetime_us_4096_naive_utc_z` | 40.691 | 40.586 | 40.590 | **39.727** |
| `datetime_us_4096_omit_microseconds` | 40.672 | 40.699 | 40.555 | **39.801** |
| `datetime_us_4096_omit_microseconds_utc_z` | 40.703 | 40.691 | 40.711 | **39.816** |
| `datetime_us_4096_utc_z` | 40.750 | 40.625 | 40.637 | **39.773** |
| `datetime_us_empty` | 40.699 | 40.797 | 40.641 | **39.766** |
| `datetime_us_matrix` | 40.645 | 40.578 | 40.590 | **39.887** |
| `datetime_us_scalar` | 40.660 | 40.688 | 40.527 | **39.766** |
| `datetime_us_under_dict` | 40.676 | 40.594 | 40.625 | **39.723** |

RSS with the first result alive (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 40.695 | 40.801 | 40.586 | **39.719** |
| `datetime_D_4096` | 40.711 | 40.723 | 40.711 | **39.773** |
| `datetime_D_scalar` | 40.625 | 40.660 | 40.535 | **39.715** |
| `datetime_M_16` | 40.625 | 40.797 | 40.586 | **39.852** |
| `datetime_M_4096` | 40.680 | 40.602 | 40.656 | **39.840** |
| `datetime_M_scalar` | 40.617 | 40.617 | 40.590 | **39.754** |
| `datetime_Y_16` | 40.605 | 40.672 | 40.594 | **39.766** |
| `datetime_Y_4096` | 40.590 | 40.664 | 40.734 | **39.832** |
| `datetime_Y_scalar` | 40.691 | 40.602 | 40.582 | **39.883** |
| `datetime_ns_16` | 40.629 | 40.586 | 40.664 | **39.770** |
| `datetime_ns_4096` | 40.660 | 40.590 | 41.141 | **39.844** |
| `datetime_ns_scalar` | 40.754 | 40.574 | 40.531 | **39.852** |
| `datetime_s_16` | 40.703 | 40.695 | 40.676 | **39.762** |
| `datetime_s_4096` | 40.668 | 40.715 | 40.598 | **39.719** |
| `datetime_s_scalar` | 40.703 | 40.617 | 40.578 | **39.844** |
| `datetime_us_16` | 40.699 | 40.695 | 40.547 | **39.777** |
| `datetime_us_4096` | 40.582 | 40.688 | 40.703 | **39.844** |
| `datetime_us_4096_naive_utc` | 41.152 | 41.152 | 41.008 | **39.727** |
| `datetime_us_4096_naive_utc_omit_microseconds` | 40.602 | 40.688 | 40.656 | **39.785** |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 40.648 | 40.645 | 40.551 | **39.801** |
| `datetime_us_4096_naive_utc_z` | 40.691 | 40.586 | 40.590 | **39.727** |
| `datetime_us_4096_omit_microseconds` | 40.672 | 40.699 | 40.555 | **39.801** |
| `datetime_us_4096_omit_microseconds_utc_z` | 40.703 | 40.691 | 40.711 | **39.816** |
| `datetime_us_4096_utc_z` | 40.750 | 40.625 | 40.637 | **39.773** |
| `datetime_us_empty` | 40.699 | 40.797 | 40.641 | **39.766** |
| `datetime_us_matrix` | 40.645 | 40.578 | 40.590 | **39.887** |
| `datetime_us_scalar` | 40.660 | 40.688 | 40.527 | **39.766** |
| `datetime_us_under_dict` | 40.676 | 40.594 | 41.117 | **39.723** |
