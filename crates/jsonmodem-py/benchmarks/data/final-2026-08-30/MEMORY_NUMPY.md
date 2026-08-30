# NumPy datetime64 memory

Original is the existing PR #3 build; Rebuilt compiles that same source
again (`b7fe329`).
Final is the changed implementation (`b0f3190`).
The reference is orjson 3.11.9. See [definitions and methods](README.md).

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
| `datetime_D_scalar` | 50 | 50 | 49 | **22** |
| `datetime_M_16` | 47 | 47 | 47 | **40** |
| `datetime_M_4096` | **48** | **48** | **48** | 4,127 |
| `datetime_M_scalar` | 50 | 50 | 49 | **22** |
| `datetime_Y_16` | 47 | 47 | 47 | **40** |
| `datetime_Y_4096` | **48** | **48** | **48** | 4,127 |
| `datetime_Y_scalar` | 50 | 50 | 49 | **22** |
| `datetime_ns_16` | 48 | 48 | 48 | **41** |
| `datetime_ns_4096` | **49** | **49** | **49** | 4,128 |
| `datetime_ns_scalar` | 51 | 51 | 50 | **23** |
| `datetime_s_16` | 47 | 47 | 47 | **40** |
| `datetime_s_4096` | **48** | **48** | **48** | 4,127 |
| `datetime_s_scalar` | 50 | 50 | 49 | **22** |
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
| `datetime_us_scalar` | 51 | 51 | 50 | **23** |
| `datetime_us_under_dict` | **52** | **52** | **52** | 4,128 |

Total allocated bytes (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 4.570 | 4.570 | 4.570 | **2.926** |
| `datetime_D_4096` | 347.258 | 347.258 | 347.258 | **332.854** |
| `datetime_D_scalar` | 3.740 | 3.740 | 3.714 | **2.601** |
| `datetime_M_16` | 4.570 | 4.570 | 4.570 | **2.926** |
| `datetime_M_4096` | 347.258 | 347.258 | 347.258 | **332.854** |
| `datetime_M_scalar` | 3.740 | 3.740 | 3.714 | **2.601** |
| `datetime_Y_16` | 4.570 | 4.570 | 4.570 | **2.926** |
| `datetime_Y_4096` | 347.258 | 347.258 | 347.258 | **332.854** |
| `datetime_Y_scalar` | 3.740 | 3.740 | 3.714 | **2.601** |
| `datetime_ns_16` | 4.722 | 4.722 | 4.722 | **3.079** |
| `datetime_ns_4096` | 375.300 | 375.300 | 375.300 | **360.898** |
| `datetime_ns_scalar` | 3.789 | 3.789 | 3.770 | **2.651** |
| `datetime_s_16` | 4.570 | 4.570 | 4.570 | **2.926** |
| `datetime_s_4096` | 347.258 | 347.258 | 347.258 | **332.854** |
| `datetime_s_scalar` | 3.740 | 3.740 | 3.714 | **2.601** |
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
| `datetime_us_scalar` | 3.789 | 3.789 | 3.770 | **2.651** |
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
| `datetime_D_16` | 37.770 | 37.688 | 37.832 | **36.758** |
| `datetime_D_4096` | 37.711 | 37.664 | 37.699 | **36.832** |
| `datetime_D_scalar` | 37.691 | 37.598 | 37.723 | **36.785** |
| `datetime_M_16` | 37.652 | 37.688 | 37.852 | **36.773** |
| `datetime_M_4096` | 37.684 | 37.680 | 37.711 | **36.809** |
| `datetime_M_scalar` | 37.664 | 37.746 | 37.742 | **36.875** |
| `datetime_Y_16` | 37.684 | 37.770 | 37.746 | **36.879** |
| `datetime_Y_4096` | 37.664 | 37.637 | 37.668 | **36.812** |
| `datetime_Y_scalar` | 37.637 | 37.664 | 37.664 | **36.730** |
| `datetime_ns_16` | 37.688 | 37.684 | 37.723 | **36.727** |
| `datetime_ns_4096` | 37.613 | 38.102 | 37.742 | **36.777** |
| `datetime_ns_scalar` | 37.660 | 37.691 | 37.750 | **36.875** |
| `datetime_s_16` | 37.648 | 37.566 | 37.812 | **36.801** |
| `datetime_s_4096` | 37.688 | 37.766 | 37.750 | **36.727** |
| `datetime_s_scalar` | 37.621 | 37.688 | 37.738 | **36.871** |
| `datetime_us_16` | 37.605 | 37.789 | 37.742 | **36.812** |
| `datetime_us_4096` | 37.688 | 38.102 | 38.246 | **36.789** |
| `datetime_us_4096_naive_utc` | 37.660 | 38.082 | 38.238 | **37.254** |
| `datetime_us_4096_naive_utc_omit_microseconds` | 37.668 | 37.684 | 38.180 | **36.789** |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 37.605 | 37.688 | 37.664 | **36.734** |
| `datetime_us_4096_naive_utc_z` | 37.637 | 38.086 | 38.387 | **36.762** |
| `datetime_us_4096_omit_microseconds` | 37.602 | 37.559 | 37.812 | **36.805** |
| `datetime_us_4096_omit_microseconds_utc_z` | 37.660 | 37.754 | 37.703 | **36.762** |
| `datetime_us_4096_utc_z` | 37.660 | 38.066 | 38.230 | **36.812** |
| `datetime_us_empty` | 37.660 | 37.738 | 37.711 | **36.805** |
| `datetime_us_matrix` | 37.656 | 38.094 | 38.184 | **36.812** |
| `datetime_us_scalar` | 37.656 | 37.758 | 37.832 | **36.684** |
| `datetime_us_under_dict` | 37.684 | 38.121 | 38.148 | **36.809** |

Prepared RSS (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 37.770 | 37.688 | 37.832 | **36.758** |
| `datetime_D_4096` | 37.711 | 37.664 | 37.699 | **36.832** |
| `datetime_D_scalar` | 37.691 | 37.598 | 37.723 | **36.785** |
| `datetime_M_16` | 37.652 | 37.688 | 37.852 | **36.773** |
| `datetime_M_4096` | 37.684 | 37.680 | 37.711 | **36.809** |
| `datetime_M_scalar` | 37.664 | 37.746 | 37.742 | **36.875** |
| `datetime_Y_16` | 37.684 | 37.770 | 37.746 | **36.879** |
| `datetime_Y_4096` | 37.664 | 37.637 | 37.668 | **36.812** |
| `datetime_Y_scalar` | 37.637 | 37.664 | 37.664 | **36.730** |
| `datetime_ns_16` | 37.688 | 37.684 | 37.723 | **36.727** |
| `datetime_ns_4096` | 37.613 | 37.609 | 37.742 | **36.777** |
| `datetime_ns_scalar` | 37.660 | 37.691 | 37.750 | **36.875** |
| `datetime_s_16` | 37.648 | 37.566 | 37.812 | **36.801** |
| `datetime_s_4096` | 37.688 | 37.766 | 37.750 | **36.727** |
| `datetime_s_scalar` | 37.621 | 37.688 | 37.738 | **36.871** |
| `datetime_us_16` | 37.605 | 37.789 | 37.742 | **36.812** |
| `datetime_us_4096` | 37.688 | 37.609 | 37.754 | **36.789** |
| `datetime_us_4096_naive_utc` | 37.660 | 37.648 | 37.805 | **36.770** |
| `datetime_us_4096_naive_utc_omit_microseconds` | 37.668 | 37.684 | 37.727 | **36.789** |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 37.605 | 37.688 | 37.664 | **36.734** |
| `datetime_us_4096_naive_utc_z` | 37.637 | 37.652 | 37.895 | **36.762** |
| `datetime_us_4096_omit_microseconds` | 37.602 | 37.559 | 37.812 | **36.805** |
| `datetime_us_4096_omit_microseconds_utc_z` | 37.660 | 37.754 | 37.703 | **36.762** |
| `datetime_us_4096_utc_z` | 37.660 | 37.633 | 37.797 | **36.812** |
| `datetime_us_empty` | 37.660 | 37.738 | 37.711 | **36.805** |
| `datetime_us_matrix` | 37.656 | 37.641 | 37.750 | **36.812** |
| `datetime_us_scalar` | 37.656 | 37.758 | 37.832 | **36.684** |
| `datetime_us_under_dict` | 37.684 | 37.688 | 37.715 | **36.809** |

RSS with the first result alive (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `datetime_D_16` | 37.770 | 37.688 | 37.832 | **36.758** |
| `datetime_D_4096` | 37.711 | 37.664 | 37.699 | **36.832** |
| `datetime_D_scalar` | 37.691 | 37.598 | 37.723 | **36.785** |
| `datetime_M_16` | 37.652 | 37.688 | 37.852 | **36.773** |
| `datetime_M_4096` | 37.684 | 37.680 | 37.711 | **36.809** |
| `datetime_M_scalar` | 37.664 | 37.746 | 37.742 | **36.875** |
| `datetime_Y_16` | 37.684 | 37.770 | 37.746 | **36.879** |
| `datetime_Y_4096` | 37.664 | 37.637 | 37.668 | **36.812** |
| `datetime_Y_scalar` | 37.637 | 37.664 | 37.664 | **36.730** |
| `datetime_ns_16` | 37.688 | 37.684 | 37.723 | **36.727** |
| `datetime_ns_4096` | 37.613 | 38.102 | 37.742 | **36.777** |
| `datetime_ns_scalar` | 37.660 | 37.691 | 37.750 | **36.875** |
| `datetime_s_16` | 37.648 | 37.566 | 37.812 | **36.801** |
| `datetime_s_4096` | 37.688 | 37.766 | 37.750 | **36.727** |
| `datetime_s_scalar` | 37.621 | 37.688 | 37.738 | **36.871** |
| `datetime_us_16` | 37.605 | 37.789 | 37.742 | **36.812** |
| `datetime_us_4096` | 37.688 | 38.102 | 38.246 | **36.789** |
| `datetime_us_4096_naive_utc` | 37.660 | 38.082 | 38.238 | **37.254** |
| `datetime_us_4096_naive_utc_omit_microseconds` | 37.668 | 37.684 | 38.180 | **36.789** |
| `datetime_us_4096_naive_utc_omit_microseconds_utc_z` | 37.605 | 37.688 | 37.664 | **36.734** |
| `datetime_us_4096_naive_utc_z` | 37.637 | 38.086 | 38.387 | **36.762** |
| `datetime_us_4096_omit_microseconds` | 37.602 | 37.559 | 37.812 | **36.805** |
| `datetime_us_4096_omit_microseconds_utc_z` | 37.660 | 37.754 | 37.703 | **36.762** |
| `datetime_us_4096_utc_z` | 37.660 | 38.066 | 38.230 | **36.812** |
| `datetime_us_empty` | 37.660 | 37.738 | 37.711 | **36.805** |
| `datetime_us_matrix` | 37.656 | 38.094 | 38.184 | **36.812** |
| `datetime_us_scalar` | 37.656 | 37.758 | 37.832 | **36.684** |
| `datetime_us_under_dict` | 37.684 | 38.121 | 38.148 | **36.809** |
