# Organized Figures Directory

This directory contains all graphical results, publication-ready vector plots (`.pdf`), and high-resolution raster images (`.png`) for the **U-AFS (Urgency-Aware Fair Scheduling)** research paper.

---

## Directory Structure

```
figures/
├── 01_main_evaluation/       # Core 16-configuration main study (64 plots: PNG & PDF)
├── 02_edca_extension/        # IEEE 802.11e EDCA baseline comparison (48 plots: PNG & PDF)
├── 03_tcp_extension/         # Closed-loop TCP Reno dynamics (40 plots: PNG & PDF)
├── 04_obss_extension/        # Multi-AP / Overlapping BSS interference sweeps (52 plots: PNG & PDF)
├── 05_ns3_extension/         # ns-3 MAC/PHY CSMA/CA contention validation
└── README_figures.md         # This documentation index
```

---

## Subfolder Details

### `01_main_evaluation/` (Section 5 of Manuscript)
Covers the 16 one-factor sensitivity configurations across 7 scheduling policies (Round-Robin, EDF, Service-DRR, Airtime-DRR, Proposed U-AFS, and ablations):
* **`reference_metrics.png / .pdf`**: Baseline performance comparison across all policies (12 stations, 18 Mbps BG load, 25 ms deadlines).
* **`reference_paired.png / .pdf`**: Per-seed paired improvements ($\Delta$ miss fraction, $\Delta$ Jain fairness) for U-AFS versus baselines.
* **`background_mbps_*_metrics.png / .pdf`**: Background offered load sweeps (6, 12, 18, 24, 30, 36 Mbps).
* **`stations_*_metrics.png / .pdf`**: Scalability sweeps across station counts (4, 8, 12, 16, 20 stations).
* **`deadline_*_metrics.png / .pdf`**: Delay tolerance / deadline tightness sweeps (10 ms, 15 ms, 25 ms, 50 ms).
* **`bad_channel_*_metrics.png / .pdf`**: Time-varying channel and fading configurations.
* **`bursty_metrics.png / .pdf`**: Performance under bursty / compound Poisson arrivals.

### `02_edca_extension/` (Section 6-A of Manuscript)
Compares U-AFS against the IEEE 802.11e EDCA Access Category prioritization standard:
* **`edca_reference_metrics.png / .pdf`**: Direct benchmark of U-AFS vs. EDCA/EDF under reference load.
* **`edca_reference_paired.png / .pdf`**: Paired per-seed comparison showing U-AFS deadline & fairness gains.
* **`edca_stations_*_metrics.png / .pdf`**: Station scaling comparison against EDCA.
* **`edca_bgload_*_metrics.png / .pdf`**: Heavy background load behavior vs. EDCA.
* **`edca_bursty_metrics.png / .pdf`**: Transient handling against EDCA under bursty conditions.

### `03_tcp_extension/` (Section 6-C of Manuscript)
Analyzes scheduler interactions with closed-loop AIMD TCP Reno traffic:
* **`tcp_reference_metrics.png / .pdf`**: Evaluates whether service debt causes TCP timeout/collapse.
* **`tcp_reference_paired.png / .pdf`**: Paired advantage of U-AFS over comparators under TCP traffic.
* **`tcp_bgload_*_metrics.png / .pdf`**: Throughput and latency across TCP background load levels.
* **`tcp_bursty_metrics.png / .pdf`**: Slow-start burst behavior and window dynamics.

### `04_obss_extension/` (Section 6-D of Manuscript)
Evaluates co-channel interference from overlapping BSSs and uplink contention:
* **`obss_reference_metrics.png / .pdf`**: Clean reference baseline without external interferers.
* **`obss_stolen_*_metrics.png / .pdf`**: Sweeps of medium stolen fraction (5%, 10%, 20%, 30%, 40% airtime loss).
* **`obss_uplink_*_metrics.png / .pdf`**: Contention impact when background traffic includes uplink stations.
* **`obss_bursty_interferer_metrics.png / .pdf`**: Unsynchronized, bursty foreign AP transmissions.

---
*Generated automatically for the U-AFS publication package.*
