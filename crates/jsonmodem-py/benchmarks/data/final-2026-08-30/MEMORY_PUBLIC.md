# Public document memory

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
| `loads:apache_builds` | 23.449 | 23.543 | 23.582 | **23.168** |
| `loads:canada` | 34.180 | **34.117** | 34.254 | 37.449 |
| `loads:citm_catalog` | 28.125 | 28.234 | **28.066** | 31.836 |
| `loads:github_events` | 23.348 | 23.207 | 22.828 | **22.727** |
| `loads:google_maps_api_response` | 22.863 | 22.730 | 22.988 | **22.375** |
| `loads:gsoc-2018` | **31.590** | 31.637 | 31.656 | 37.621 |
| `loads:instruments` | **23.449** | 23.625 | 23.621 | 23.676 |
| `loads:marine_ik` | **36.824** | 37.039 | 37.086 | 44.102 |
| `loads:mesh` | 26.707 | **26.438** | 26.758 | 28.762 |
| `loads:numbers` | 23.445 | 23.508 | 23.543 | **23.223** |
| `loads:otfcc` | 707.680 | 707.652 | **707.645** | 871.758 |
| `loads:poet` | 32.316 | 32.270 | **32.148** | 39.102 |
| `loads:random` | **25.930** | 25.984 | 26.004 | 29.211 |
| `loads:semanticscholar-corpus` | 53.719 | 53.566 | **53.453** | 69.207 |
| `loads:tree-pretty` | 22.777 | 22.762 | 22.992 | **22.270** |
| `loads:twitter` | 24.574 | **24.453** | 24.594 | 26.316 |
| `loads:twitterescaped` | **24.441** | 24.652 | 24.617 | 26.676 |
| `loads:update-center` | **25.066** | 26.195 | 26.340 | 26.660 |
| `dumps:apache_builds` | 23.500 | 23.402 | 23.465 | **22.852** |
| `dumps:canada` | 36.125 | 36.035 | 36.027 | **35.422** |
| `dumps:citm_catalog` | 31.102 | 31.059 | 31.090 | **30.656** |
| `dumps:github_events` | 23.180 | 23.250 | 23.289 | **22.512** |
| `dumps:google_maps_api_response` | 22.922 | 22.719 | 22.895 | **22.309** |
| `dumps:gsoc-2018` | 35.719 | 35.727 | 36.195 | **33.609** |
| `dumps:instruments` | 23.352 | 23.512 | 23.547 | **22.809** |
| `dumps:marine_ik` | 39.566 | 39.520 | 39.742 | **39.402** |
| `dumps:mesh` | 27.996 | 28.004 | 27.953 | **26.418** |
| `dumps:numbers` | 23.758 | 23.867 | 23.898 | **22.707** |
| `dumps:otfcc` | 714.039 | 713.832 | 713.801 | **713.293** |
| `dumps:poet` | 38.008 | 38.105 | 38.109 | **37.367** |
| `dumps:random` | 26.227 | 26.238 | 26.398 | **26.223** |
| `dumps:semanticscholar-corpus` | 85.574 | 85.539 | 85.441 | **85.180** |
| `dumps:tree-pretty` | 22.777 | 22.812 | 22.828 | **22.270** |
| `dumps:twitter` | 26.652 | 26.621 | 26.574 | **25.895** |
| `dumps:twitterescaped` | 25.051 | 24.938 | 25.191 | **24.453** |
| `dumps:update-center` | 26.078 | 26.074 | 25.922 | **25.363** |

Prepared RSS (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads:apache_builds` | 22.762 | 22.855 | 22.895 | **22.250** |
| `loads:canada` | 24.980 | 24.883 | 25.113 | **24.398** |
| `loads:citm_catalog` | 24.434 | 24.547 | 24.422 | **23.887** |
| `loads:github_events` | 22.918 | 22.777 | 22.828 | **22.332** |
| `loads:google_maps_api_response` | 22.863 | 22.730 | 22.988 | **22.375** |
| `loads:gsoc-2018` | 25.941 | 26.004 | 26.078 | **25.324** |
| `loads:instruments` | 23.074 | 23.250 | 22.934 | **22.566** |
| `loads:marine_ik` | 25.602 | 25.812 | 25.883 | **25.145** |
| `loads:mesh` | 23.496 | 23.227 | 23.547 | **22.809** |
| `loads:numbers` | 22.758 | 22.820 | 22.855 | **22.309** |
| `loads:otfcc` | 86.277 | 86.168 | 86.176 | **85.566** |
| `loads:poet` | 26.270 | 26.223 | 26.211 | **25.535** |
| `loads:random` | 23.398 | 23.492 | 23.566 | **22.809** |
| `loads:semanticscholar-corpus` | 31.312 | 31.188 | 31.074 | **30.531** |
| `loads:tree-pretty` | 22.777 | 22.762 | 22.992 | **22.270** |
| `loads:twitter` | 23.426 | 23.305 | 23.445 | **22.742** |
| `loads:twitterescaped` | 23.293 | 23.504 | 23.469 | **22.715** |
| `loads:update-center` | 23.402 | 23.500 | 23.645 | **22.797** |
| `dumps:apache_builds` | 23.500 | 23.402 | 23.465 | **22.852** |
| `dumps:canada` | 32.047 | 31.949 | 31.891 | **31.305** |
| `dumps:citm_catalog` | 26.215 | 26.191 | 26.203 | **25.727** |
| `dumps:github_events` | 23.180 | 23.250 | 23.289 | **22.512** |
| `dumps:google_maps_api_response` | 22.922 | 22.719 | 22.895 | **22.309** |
| `dumps:gsoc-2018` | 28.191 | 28.062 | 27.965 | **27.457** |
| `dumps:instruments` | 23.352 | 23.512 | 23.547 | **22.809** |
| `dumps:marine_ik` | 34.023 | 33.973 | 34.152 | **33.770** |
| `dumps:mesh` | 27.105 | 27.113 | 27.062 | **26.418** |
| `dumps:numbers` | 23.324 | 23.492 | 23.465 | **22.707** |
| `dumps:otfcc` | 522.391 | 522.180 | 522.152 | **521.648** |
| `dumps:poet` | 28.156 | 28.254 | 28.258 | **27.547** |
| `dumps:random` | **25.102** | 25.113 | 25.230 | 25.645 |
| `dumps:semanticscholar-corpus` | 45.230 | 45.195 | 45.094 | **44.586** |
| `dumps:tree-pretty` | 22.777 | 22.812 | 22.828 | **22.270** |
| `dumps:twitter` | 24.637 | 24.605 | 24.555 | **23.898** |
| `dumps:twitterescaped` | 25.051 | 24.621 | 24.816 | **24.137** |
| `dumps:update-center` | 25.195 | 25.188 | 24.988 | **24.449** |

RSS with the first result alive (Linux VmRSS) (MiB). Lower is better.

| Case | Original | Rebuilt | Final | orjson |
| --- | ---: | ---: | ---: | ---: |
| `loads:apache_builds` | 23.449 | 23.543 | 23.324 | **22.914** |
| `loads:canada` | 34.121 | 34.023 | 34.254 | **32.703** |
| `loads:citm_catalog` | 27.902 | 28.016 | 27.891 | **27.480** |
| `loads:github_events` | 23.348 | 22.777 | 22.828 | **22.727** |
| `loads:google_maps_api_response` | 22.863 | 22.730 | 22.988 | **22.375** |
| `loads:gsoc-2018` | 31.215 | 31.277 | 31.352 | **30.602** |
| `loads:instruments` | 23.449 | 23.625 | 23.621 | **23.027** |
| `loads:marine_ik` | 36.801 | 37.016 | 37.086 | **36.398** |
| `loads:mesh` | 26.707 | 26.438 | 26.758 | **25.957** |
| `loads:numbers` | 23.445 | 23.508 | 23.543 | **22.969** |
| `loads:otfcc` | 707.465 | 707.512 | 707.621 | **582.477** |
| `loads:poet` | 32.316 | 32.270 | 32.059 | **30.859** |
| `loads:random` | 25.578 | 25.672 | 25.488 | **25.156** |
| `loads:semanticscholar-corpus` | 53.598 | 53.473 | **53.359** | 55.781 |
| `loads:tree-pretty` | 22.777 | 22.762 | 22.992 | **22.270** |
| `loads:twitter` | 24.574 | 24.453 | 24.594 | **24.055** |
| `loads:twitterescaped` | 24.184 | 24.395 | 24.359 | **23.953** |
| `loads:update-center` | 25.066 | 25.164 | 25.309 | **24.660** |
| `dumps:apache_builds` | 23.500 | 23.402 | 23.465 | **22.852** |
| `dumps:canada` | 36.027 | 35.988 | 35.875 | **33.164** |
| `dumps:citm_catalog` | 27.102 | 27.078 | 27.090 | **26.078** |
| `dumps:github_events` | 23.180 | 23.250 | 23.289 | **22.512** |
| `dumps:google_maps_api_response` | 22.922 | 22.719 | 22.895 | **22.309** |
| `dumps:gsoc-2018` | 32.059 | **31.930** | 32.008 | 33.609 |
| `dumps:instruments` | 23.352 | 23.512 | 23.547 | **22.809** |
| `dumps:marine_ik` | 37.488 | 37.477 | 37.617 | **35.371** |
| `dumps:mesh` | 27.996 | 28.004 | 27.953 | **26.418** |
| `dumps:numbers` | 23.758 | 23.867 | 23.898 | **22.707** |
| `dumps:otfcc` | 586.867 | 586.680 | 586.684 | **585.914** |
| `dumps:poet` | 37.484 | 37.582 | 37.395 | **35.094** |
| `dumps:random` | **25.988** | 26.000 | 26.117 | 26.223 |
| `dumps:semanticscholar-corpus` | 66.430 | 66.449 | 66.281 | **55.371** |
| `dumps:tree-pretty` | 22.777 | 22.812 | 22.828 | **22.270** |
| `dumps:twitter` | 25.266 | 25.234 | 25.184 | **23.898** |
| `dumps:twitterescaped` | 25.051 | 24.938 | 25.191 | **24.453** |
| `dumps:update-center` | 25.824 | 25.816 | 25.617 | **24.820** |

Successful worker stderr is not retained by the unchanged public driver. Coordinator stderr cannot establish that each worker was silent.
