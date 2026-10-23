# Organized Tables Directory

This directory contains all numerical datasets, summary metrics, statistical hypothesis test results (Wilcoxon signed-rank with Holm-Bonferroni correction), and configuration metadata for the **U-AFS (Urgency-Aware Fair Scheduling)** research paper.

---

## Directory Structure

```
tables/
├── 01_main_evaluation/       # Core 16-configuration main study (6 CSV & Markdown files)
├── 02_edca_extension/        # IEEE 802.11e EDCA baseline comparison (6 CSV & Markdown files)
├── 03_tcp_extension/         # Closed-loop TCP Reno dynamics (6 CSV & Markdown files)
├── 04_obss_extension/        # Multi-AP / Overlapping BSS interference sweeps (6 CSV & Markdown files)
├── 05_ns3_extension/         # ns-3 MAC/PHY CSMA/CA contention validation (JSON & CSV)
└── README_tables.md          # This documentation index
```

---

## File Contents Within Each Subfolder

Each subfolder contains standardized evaluation outputs:

1. **`summary.csv` & `summary.md`**:
   * Aggregated mean, standard deviation, and 95% bootstrap confidence intervals for all evaluated policies.
   * Primary metrics: `rt_miss_fraction`, `service_jain`, `airtime_jain`, `bg_goodput_mbps`, `bg_delivery_fraction`, `rt_p99_ms`, and `bg_p95_delay_ms`.
2. **`comparisons.csv` & `comparisons.md`**:
   * Statistical hypothesis tests comparing U-AFS against each baseline (Round-Robin, EDF, Service-DRR, Airtime-DRR, EDCA).
   * Reports mean paired difference, bootstrap 95% CI of the difference, Wilcoxon signed-rank test statistic, p-value, and Holm-Bonferroni significance indicator.
3. **`configurations.csv`**:
   * Exact parameters for each test scenario (stations, load, deadline, channel multipliers, queue limits, duration, seeds).
4. **`all_runs.csv`**:
   * Raw per-seed metrics for every individual simulation run across all random seeds (allowing complete independent re-analysis).

---

## Subfolder Mapping to Paper Sections

| Folder | Paper Section | Primary Focus |
| :--- | :--- | :--- |
| **`01_main_evaluation/`** | Section 5 (Main Evaluation) | 16-configuration evaluation across 40 seeds (4,480 total simulation runs). Includes reference, station sweeps, load sweeps, channel variations, and ablations. |
| **`02_edca_extension/`** | Section 6-A (EDCA Baseline) | Comparison of U-AFS against strict Access Category prioritization (IEEE 802.11e EDCA standard). |
| **`03_tcp_extension/`** | Section 6-C (TCP Background) | Evaluation with closed-loop AIMD TCP Reno traffic reacting to queuing delay and packet loss. |
| **`04_obss_extension/`** | Section 6-D (OBSS Multi-AP) | Evaluation under co-channel interference from external APs and uplink contending stations (0% to 40% stolen airtime). |
| **`05_ns3_extension/`** | Section 6-E (ns-3 Bridge) | Validation of CSMA/CA contention, random backoff slots, and capture effects modeled via Bianchi collision formulations and ns-3. |

---
*Generated automatically for the U-AFS publication package.*
