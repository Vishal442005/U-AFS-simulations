# Table 1: SOTA & Classical Baseline Comparison under Reference Scenario

*Configuration: N=12 stations, 18 Mbps BG load, D=25 ms deadline, 20 independent seeds.*

| Policy                        | RT Miss (%) [95% CI]   |   Mean Miss (%) |   RT p99 Delay (ms) |   BG Goodput (Mbps) |   Service Jain |   Airtime Jain |
|:------------------------------|:-----------------------|----------------:|--------------------:|--------------------:|---------------:|---------------:|
| U-AFS (Proposed)              | 10.28 ± 0.45           |           10.28 |               19.08 |               11.3  |          0.998 |          0.966 |
| LSDSF (ACM MobiHoc '24)       | 17.59 ± 1.08           |           17.59 |               24.86 |               11.76 |          0.847 |          0.784 |
| Lyapunov (IEEE/ACM ToN '24)   | 25.05 ± 1.67           |           25.05 |               15.65 |               12.41 |          0.851 |          0.788 |
| EXP-Rule (Shakkottai et al.)  | 16.01 ± 0.81           |           16.01 |                3.87 |               12.02 |          0.865 |          0.816 |
| M-LWDF (Andrews et al.)       | 84.41 ± 0.80           |           84.41 |               24.94 |               15.32 |          0.885 |          0.799 |
| Earliest Deadline First (EDF) | 15.54 ± 0.86           |           15.54 |                6.34 |                7.84 |          0.847 |          0.748 |
| IEEE 802.11e EDCA             | 15.54 ± 0.86           |           15.54 |                6.34 |                7.84 |          0.847 |          0.748 |
| Service-DRR                   | 63.71 ± 0.95           |           63.71 |               24.77 |               14.78 |          0.995 |          0.948 |
| Round-Robin                   | 98.64 ± 0.22           |           98.64 |               24.94 |               13.19 |          0.798 |          0.714 |
