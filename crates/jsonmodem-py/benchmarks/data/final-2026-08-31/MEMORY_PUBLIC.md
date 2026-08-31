# Public document memory

[Summary](PERFORMANCE_FINAL.md). Medians of three process observations.
Memray uses one tracked call after ten warmups.
Peak live bytes are Memray's reported capture peak, not process RSS or a separate reconstruction.
RSS uses ten calls without warmup. Peak RSS is Linux VmHWM, including preparation; it is not ru_maxrss.
Four libraries and three repetitions do not fully balance execution positions. There is no memory mean.

Allocation requests (requests). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads:apache_builds` | 4,308 | 4,308 | 4,308 | **4,255** |
| `loads:canada` | 225,411 | 225,411 | 225,411 | **223,043** |
| `loads:citm_catalog` | 51,213 | 51,213 | 51,213 | **49,014** |
| `loads:github_events` | 1,230 | 1,230 | 1,230 | **1,081** |
| `loads:google_maps_api_response` | 1,024 | 1,024 | 1,024 | **985** |
| `loads:gsoc-2018` | 25,164 | 25,164 | 25,164 | **23,200** |
| `loads:instruments` | 2,797 | 2,797 | 2,797 | **2,490** |
| `loads:marine_ik` | 257,531 | 257,531 | 257,531 | **255,899** |
| `loads:mesh` | 74,385 | 74,385 | 74,385 | **74,104** |
| `loads:numbers` | 9,956 | 9,956 | 9,956 | **9,911** |
| `loads:otfcc` | 10,276,965 | 10,276,965 | 10,276,965 | **7,375,455** |
| `loads:poet` | 80,375 | 80,375 | 80,375 | **44,514** |
| `loads:random` | 32,564 | 32,564 | 32,564 | **23,519** |
| `loads:semanticscholar-corpus` | 249,836 | 249,836 | 249,836 | **230,416** |
| `loads:tree-pretty` | 556 | 556 | 556 | **467** |
| `loads:twitter` | 11,551 | 11,551 | 11,551 | **9,237** |
| `loads:twitterescaped` | 11,551 | 11,551 | 11,551 | **9,237** |
| `loads:update-center` | 20,803 | 20,803 | 20,803 | **19,583** |
| `dumps:apache_builds` | 23 | 23 | 23 | **15** |
| `dumps:canada` | 25 | 25 | 25 | **20** |
| `dumps:citm_catalog` | 26 | 26 | 26 | **18** |
| `dumps:github_events` | 23 | 23 | 23 | **14** |
| `dumps:google_maps_api_response` | 20 | 20 | 20 | **13** |
| `dumps:gsoc-2018` | 28 | 28 | 28 | **18** |
| `dumps:instruments` | 24 | 24 | 24 | **16** |
| `dumps:marine_ik` | 29 | 29 | 29 | **20** |
| `dumps:mesh` | 25 | 25 | 25 | **19** |
| `dumps:numbers` | 20 | 20 | 20 | **17** |
| `dumps:otfcc` | 34 | 34 | 34 | **25** |
| `dumps:poet` | 24 | 24 | 24 | **19** |
| `dumps:random` | 26 | 26 | 26 | **18** |
| `dumps:semanticscholar-corpus` | 31 | 31 | 31 | **22** |
| `dumps:tree-pretty` | 22 | 22 | 22 | **13** |
| `dumps:twitter` | 27 | 27 | 27 | **17** |
| `dumps:twitterescaped` | 27 | 27 | 27 | **17** |
| `dumps:update-center` | 27 | 27 | 27 | **19** |

Total allocated bytes (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads:apache_builds` | **378.474** | **378.474** | **378.474** | 1,814.337 |
| `loads:canada` | **10,738.328** | **10,738.328** | **10,738.328** | 33,349.704 |
| `loads:citm_catalog` | **3,340.862** | **3,340.862** | **3,340.862** | 23,366.715 |
| `loads:github_events` | **139.625** | **139.625** | **139.625** | 868.387 |
| `loads:google_maps_api_response` | **67.538** | **67.538** | **67.538** | 371.432 |
| `loads:gsoc-2018` | **7,164.885** | **7,164.885** | **7,164.885** | 43,951.670 |
| `loads:instruments` | **348.934** | **348.934** | **348.934** | 2,883.679 |
| `loads:marine_ik` | **19,724.080** | **19,724.080** | **19,724.080** | 44,629.881 |
| `loads:mesh` | **7,217.479** | **7,217.479** | **7,217.479** | 10,991.023 |
| `loads:numbers` | **965.242** | **965.242** | **965.242** | 2,070.750 |
| `loads:otfcc` | **637,223.324** | **637,223.324** | **637,223.324** | 1,254,853.313 |
| `loads:poet` | **15,476.084** | **15,476.084** | **15,476.084** | 46,293.930 |
| `loads:random` | **2,885.770** | **2,885.770** | **2,885.770** | 8,056.793 |
| `loads:semanticscholar-corpus` | **27,938.461** | **27,938.461** | **27,938.461** | 124,340.575 |
| `loads:tree-pretty` | **55.303** | **55.303** | **55.303** | 450.474 |
| `loads:twitter` | **1,527.312** | **1,527.312** | **1,527.312** | 8,415.667 |
| `loads:twitterescaped` | **1,527.312** | **1,527.312** | **1,527.312** | 7,603.667 |
| `loads:update-center` | **1,734.847** | **1,734.847** | **1,734.847** | 7,828.011 |
| `dumps:apache_builds` | 383.619 | 383.619 | 383.619 | **253.788** |
| `dumps:canada` | 6,138.339 | 6,138.339 | 6,138.339 | **4,095.949** |
| `dumps:citm_catalog` | 1,514.324 | 1,514.324 | 1,514.324 | **1,023.885** |
| `dumps:github_events` | 181.830 | 181.830 | 181.830 | **95.756** |
| `dumps:google_maps_api_response` | 44.911 | 44.911 | 44.911 | **31.724** |
| `dumps:gsoc-2018` | 13,698.729 | 13,698.729 | 13,698.729 | **8,165.885** |
| `dumps:instruments` | 363.525 | 363.525 | 363.525 | **255.820** |
| `dumps:marine_ik` | 5,884.282 | 5,884.282 | 5,884.282 | **4,095.949** |
| `dumps:mesh` | 2,684.204 | 2,684.204 | 2,684.204 | **2,047.917** |
| `dumps:numbers` | 658.948 | 658.948 | 658.948 | **511.853** |
| `dumps:otfcc` | 195,927.585 | 195,927.585 | 195,927.585 | **131,072.110** |
| `dumps:poet` | 10,125.254 | 10,125.254 | 10,125.254 | **8,185.917** |
| `dumps:random` | 1,476.401 | 1,476.401 | 1,476.401 | **1,023.885** |
| `dumps:semanticscholar-corpus` | 41,156.812 | 41,156.812 | 41,156.812 | **32,764.014** |
| `dumps:tree-pretty` | 49.268 | 49.268 | 49.268 | **31.724** |
| `dumps:twitter` | 1,550.681 | 1,550.681 | 1,550.681 | **1,021.853** |
| `dumps:twitterescaped` | 1,550.681 | 1,550.681 | 1,550.681 | **1,021.853** |
| `dumps:update-center` | 2,570.219 | 2,570.219 | 2,570.219 | **2,047.917** |

Peak live bytes tracked by Memray (KiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads:apache_builds` | **325.196** | **325.196** | **325.196** | 1,814.087 |
| `loads:canada` | **7,873.465** | **7,873.465** | **7,873.465** | 33,349.454 |
| `loads:citm_catalog` | **3,219.961** | **3,219.961** | **3,219.961** | 23,366.465 |
| `loads:github_events` | **119.281** | **119.281** | **119.281** | 868.137 |
| `loads:google_maps_api_response` | **65.589** | **65.589** | **65.589** | 371.182 |
| `loads:gsoc-2018` | **5,007.377** | **5,007.377** | **5,007.377** | 43,951.420 |
| `loads:instruments` | **278.734** | **278.734** | **278.734** | 2,883.429 |
| `loads:marine_ik` | **10,160.085** | **10,160.085** | **10,160.085** | 44,629.631 |
| `loads:mesh` | **2,720.655** | **2,720.655** | **2,720.655** | 10,990.773 |
| `loads:numbers` | **315.492** | **315.492** | **315.492** | 2,070.500 |
| `loads:otfcc` | **600,033.339** | **600,033.339** | **600,033.339** | 1,254,853.063 |
| `loads:poet` | **5,130.001** | **5,130.001** | **5,130.001** | 46,293.680 |
| `loads:random` | **1,921.479** | **1,921.479** | **1,921.479** | 8,056.543 |
| `loads:semanticscholar-corpus` | **20,820.381** | **20,820.381** | **20,820.381** | 124,340.325 |
| `loads:tree-pretty` | **40.626** | **40.626** | **40.626** | 450.224 |
| `loads:twitter` | **913.774** | **913.774** | **913.774** | 8,415.417 |
| `loads:twitterescaped` | **913.774** | **913.774** | **913.774** | 7,603.417 |
| `loads:update-center` | **1,551.969** | **1,551.969** | **1,551.969** | 7,827.761 |
| `dumps:apache_builds` | 238.154 | 238.154 | 238.154 | **128.345** |
| `dumps:canada` | 4,089.589 | 4,089.589 | 4,089.589 | **2,048.345** |
| `dumps:citm_catalog` | 1,001.293 | 1,001.293 | 1,001.293 | **512.345** |
| `dumps:github_events` | 116.799 | 116.799 | 116.799 | **64.345** |
| `dumps:google_maps_api_response` | 28.067 | 28.067 | 28.067 | **16.345** |
| `dumps:gsoc-2018` | 8,348.811 | 8,348.811 | 8,348.811 | **4,096.345** |
| `dumps:instruments` | 234.494 | 234.494 | 234.494 | **128.345** |
| `dumps:marine_ik` | 3,834.251 | 3,834.251 | 3,834.251 | **2,048.345** |
| `dumps:mesh` | 1,659.860 | 1,659.860 | 1,659.860 | **1,024.345** |
| `dumps:numbers` | 402.948 | 402.948 | 402.948 | **256.345** |
| `dumps:otfcc` | 130,389.554 | 130,389.554 | 130,389.554 | **65,536.345** |
| `dumps:poet` | 6,673.597 | 6,673.597 | 6,673.597 | **4,096.345** |
| `dumps:random` | 963.370 | 963.370 | 963.370 | **512.345** |
| `dumps:semanticscholar-corpus` | 24,771.780 | 24,771.780 | 24,771.780 | **16,384.345** |
| `dumps:tree-pretty` | 31.236 | 31.236 | 31.236 | **16.345** |
| `dumps:twitter` | 1,002.683 | 1,002.683 | 1,002.683 | **512.345** |
| `dumps:twitterescaped` | 1,002.683 | 1,002.683 | 1,002.683 | **512.345** |
| `dumps:update-center` | 1,545.188 | 1,545.188 | 1,545.188 | **1,024.345** |

Peak RSS, including preparation (Linux VmHWM) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads:apache_builds` | 23.656 | 23.582 | 23.582 | **23.273** |
| `loads:canada` | **34.094** | 34.277 | 34.102 | 41.223 |
| `loads:citm_catalog` | 28.156 | 28.234 | **28.152** | 31.926 |
| `loads:github_events` | 22.891 | 22.891 | 22.883 | **22.660** |
| `loads:google_maps_api_response` | 22.879 | 22.895 | 22.945 | **22.211** |
| `loads:gsoc-2018` | **31.379** | 31.508 | 31.535 | 37.684 |
| `loads:instruments` | 23.684 | 23.539 | **23.531** | 23.668 |
| `loads:marine_ik` | 36.918 | **36.832** | 37.059 | 46.035 |
| `loads:mesh` | **26.672** | 26.762 | 26.793 | 29.199 |
| `loads:numbers` | 23.660 | 23.617 | 23.633 | **23.270** |
| `loads:otfcc` | 707.762 | 707.719 | **707.668** | 871.754 |
| `loads:poet` | 32.363 | **32.270** | 32.352 | 38.504 |
| `loads:random` | **25.934** | 25.984 | 26.012 | 29.316 |
| `loads:semanticscholar-corpus` | **53.582** | 53.676 | 53.629 | 72.719 |
| `loads:tree-pretty` | 22.984 | 22.918 | 22.875 | **22.266** |
| `loads:twitter` | 24.707 | **24.484** | 24.730 | 26.715 |
| `loads:twitterescaped` | **24.645** | 24.715 | 24.664 | 26.906 |
| `loads:update-center` | **26.156** | 26.211 | 26.215 | 27.473 |
| `dumps:apache_builds` | 23.543 | 23.551 | 23.477 | **22.707** |
| `dumps:canada` | 36.207 | 35.996 | 36.156 | **35.480** |
| `dumps:citm_catalog` | 31.055 | 31.086 | 31.168 | **30.500** |
| `dumps:github_events` | 23.203 | 23.191 | 23.180 | **22.465** |
| `dumps:google_maps_api_response` | 22.980 | 22.719 | 22.957 | **22.324** |
| `dumps:gsoc-2018` | 35.582 | 35.477 | 36.254 | **33.586** |
| `dumps:instruments` | 23.547 | 23.336 | 23.512 | **22.805** |
| `dumps:marine_ik` | 39.672 | 39.645 | 39.633 | **39.395** |
| `dumps:mesh` | 28.047 | 27.973 | 27.922 | **26.473** |
| `dumps:numbers` | 23.875 | 23.770 | 23.918 | **22.781** |
| `dumps:otfcc` | 713.938 | 713.969 | 713.957 | **713.285** |
| `dumps:poet` | 38.102 | 37.875 | 37.734 | **37.340** |
| `dumps:random` | 26.352 | **26.230** | 26.348 | 26.297 |
| `dumps:semanticscholar-corpus` | 85.445 | 85.438 | 85.641 | **85.203** |
| `dumps:tree-pretty` | 22.988 | 22.887 | 22.910 | **22.281** |
| `dumps:twitter` | 26.570 | 26.469 | 26.586 | **25.918** |
| `dumps:twitterescaped` | 25.215 | 25.211 | 25.234 | **24.391** |
| `dumps:update-center` | 25.922 | 26.133 | 26.004 | **25.469** |

Prepared RSS (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads:apache_builds` | 22.969 | 22.895 | 22.895 | **22.348** |
| `loads:canada` | 24.883 | 25.008 | 24.891 | **24.363** |
| `loads:citm_catalog` | 24.527 | 24.590 | 24.496 | **23.922** |
| `loads:github_events` | 22.891 | 22.891 | 22.883 | **22.266** |
| `loads:google_maps_api_response` | 22.879 | 22.895 | 22.945 | **22.211** |
| `loads:gsoc-2018` | 25.848 | 25.977 | 26.004 | **25.367** |
| `loads:instruments` | 22.996 | 22.852 | 23.113 | **22.414** |
| `loads:marine_ik` | 25.703 | 25.629 | 25.797 | **25.086** |
| `loads:mesh` | 23.461 | 23.551 | 23.523 | **22.777** |
| `loads:numbers` | 22.973 | 22.930 | 22.910 | **22.328** |
| `loads:otfcc` | 86.215 | 86.090 | 86.172 | **85.473** |
| `loads:poet` | 26.328 | 26.223 | 26.305 | **25.641** |
| `loads:random` | 23.496 | 23.547 | 23.516 | **22.891** |
| `loads:semanticscholar-corpus` | 31.180 | 31.277 | 31.195 | **30.438** |
| `loads:tree-pretty` | 22.984 | 22.918 | 22.875 | **22.266** |
| `loads:twitter` | 23.559 | 23.336 | 23.523 | **22.820** |
| `loads:twitterescaped` | 23.496 | 23.566 | 23.457 | **22.895** |
| `loads:update-center` | 23.461 | 23.516 | 23.461 | **22.781** |
| `dumps:apache_builds` | 23.543 | 23.551 | 23.477 | **22.707** |
| `dumps:canada` | 32.109 | 31.863 | 32.027 | **31.367** |
| `dumps:citm_catalog` | 26.172 | 26.289 | 26.289 | **25.562** |
| `dumps:github_events` | 23.203 | 23.191 | 23.180 | **22.465** |
| `dumps:google_maps_api_response` | 22.980 | 22.719 | 22.957 | **22.324** |
| `dumps:gsoc-2018` | 28.059 | 28.094 | 28.023 | **27.410** |
| `dumps:instruments` | 23.547 | 23.336 | 23.512 | **22.805** |
| `dumps:marine_ik` | 34.090 | 34.059 | 34.043 | **33.758** |
| `dumps:mesh` | 27.156 | 27.031 | 27.031 | **26.473** |
| `dumps:numbers` | 23.500 | 23.395 | 23.484 | **22.781** |
| `dumps:otfcc` | 522.262 | 522.363 | 522.273 | **521.613** |
| `dumps:poet` | 28.254 | 28.027 | 28.125 | **27.520** |
| `dumps:random` | 25.180 | **25.055** | 25.180 | 25.691 |
| `dumps:semanticscholar-corpus` | 45.102 | 45.090 | 45.270 | **44.613** |
| `dumps:tree-pretty` | 22.988 | 22.887 | 22.910 | **22.281** |
| `dumps:twitter` | 24.555 | 24.449 | 24.574 | **23.922** |
| `dumps:twitterescaped` | 24.840 | 24.836 | 24.801 | **24.074** |
| `dumps:update-center` | 25.000 | 25.203 | 25.082 | **24.551** |

RSS with the first result alive (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads:apache_builds` | 23.398 | 23.324 | 23.324 | **23.020** |
| `loads:canada` | 34.023 | 34.148 | 34.082 | **32.668** |
| `loads:citm_catalog` | 27.996 | 28.059 | 27.965 | **27.555** |
| `loads:github_events` | 22.891 | 22.891 | 22.883 | **22.660** |
| `loads:google_maps_api_response` | 22.879 | 22.895 | 22.945 | **22.211** |
| `loads:gsoc-2018` | 31.121 | 30.992 | 31.109 | **30.621** |
| `loads:instruments` | 23.504 | 23.281 | 23.531 | **23.137** |
| `loads:marine_ik` | 36.906 | 36.832 | 37.059 | **36.316** |
| `loads:mesh` | 26.672 | 26.762 | 26.793 | **25.918** |
| `loads:numbers` | 23.660 | 23.617 | 23.633 | **23.016** |
| `loads:otfcc` | 707.637 | 707.445 | 707.590 | **582.469** |
| `loads:poet` | 32.363 | 32.270 | 32.254 | **30.996** |
| `loads:random` | 25.418 | 25.469 | 25.496 | **25.262** |
| `loads:semanticscholar-corpus` | **53.465** | 53.562 | 53.539 | 55.695 |
| `loads:tree-pretty` | 22.984 | 22.918 | 22.875 | **22.266** |
| `loads:twitter` | 24.707 | 24.484 | 24.730 | **24.105** |
| `loads:twitterescaped` | 24.387 | 24.457 | 24.406 | **24.141** |
| `loads:update-center` | 25.125 | 25.180 | 25.184 | **24.605** |
| `dumps:apache_builds` | 23.543 | 23.551 | 23.477 | **22.707** |
| `dumps:canada` | 36.090 | 35.902 | 36.066 | **33.227** |
| `dumps:citm_catalog` | 27.059 | 27.176 | 27.176 | **25.875** |
| `dumps:github_events` | 23.203 | 23.191 | 23.180 | **22.465** |
| `dumps:google_maps_api_response` | 22.980 | 22.719 | 22.957 | **22.324** |
| `dumps:gsoc-2018` | 31.918 | 32.012 | **31.887** | 33.555 |
| `dumps:instruments` | 23.547 | 23.336 | 23.512 | **22.805** |
| `dumps:marine_ik` | 37.555 | 37.582 | 37.566 | **35.363** |
| `dumps:mesh` | 28.047 | 27.973 | 27.922 | **26.473** |
| `dumps:numbers` | 23.875 | 23.770 | 23.918 | **22.781** |
| `dumps:otfcc` | 586.734 | 586.836 | 586.816 | **585.914** |
| `dumps:poet` | 37.391 | 37.355 | 37.453 | **35.402** |
| `dumps:random` | 26.066 | **25.941** | 26.105 | 26.297 |
| `dumps:semanticscholar-corpus` | 67.504 | 67.762 | 67.160 | **58.879** |
| `dumps:tree-pretty` | 22.988 | 22.887 | 22.910 | **22.281** |
| `dumps:twitter` | 25.242 | 25.137 | 25.309 | **23.922** |
| `dumps:twitterescaped` | 25.215 | 25.211 | 25.234 | **24.391** |
| `dumps:update-center` | 25.629 | 25.832 | 25.711 | **24.863** |

Successful worker stderr is not retained by the unchanged public driver. Coordinator stderr cannot establish that each worker was silent.
