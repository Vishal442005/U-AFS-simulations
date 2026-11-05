# Publication Figures Directory

This directory contains the publication-ready vector plots (`.pdf`) for the **U-AFS (Urgency-Aware Fair Scheduling)** research paper.

---

## Directory Structure

```
figures/
├── 00_architectural_diagrams/  # System architecture, decision flowcharts, radar charts, SOTA landscape
├── 01_main_evaluation/         # Core 16-configuration main study (distributions & paired differences)
├── 02_edca_extension/          # IEEE 802.11e EDCA baseline comparison
├── 03_tcp_extension/           # Closed-loop AIMD TCP Reno transport dynamics
├── 04_obss_extension/          # Multi-AP / Overlapping BSS (OBSS) co-channel interference sweeps
└── README.md                   # This documentation index
```

---

## Vector PDF Inventory (26 Figures)

### 00_architectural_diagrams/
* `fig1_uafs_system_architecture.pdf`: High-level system architecture of U-AFS in an IEEE 802.11 Access Point.
* `fig2_uafs_decision_flowchart.pdf`: Three-stage scheduling decision logic flowchart.
* `fig12_spsa_autotuning_architecture.pdf`: Closed-loop Simultaneous Perturbation Stochastic Approximation (SPSA) control loop.
* `fig13_obss_ns3_validation_framework.pdf`: Cross-layer multi-AP contention and full-stack ns-3 discrete-event co-simulation framework.
* `fig14_pareto_multimetric_radar.pdf`: 7-metric Pareto trade-off radar chart across all scheduling paradigms.
* `fig15_parameter_sensitivity_surface.pdf`: 2D objective function response surface over urgency horizon $H_u$ and fairness weight $w_f$.
* `fig16_cross_factor_phase_transitions.pdf`: Continuous multi-factor phase transitions across load, deadline, and channel fading.
* `fig17_microscopic_scheduling_trace.pdf`: Microscopic 100-ms scheduling execution trace.
* `fig18_dynamic_online_spsa_tracking.pdf`: Dynamic online SPSA tracking under non-stationary traffic surges and fading drift.
* `fig20_sota_2025_2026_comparative_landscape.pdf`: Qualitative architectural taxonomy and 2024–2026 state-of-the-art comparative landscape.

### 01_main_evaluation/
* `fig1_reference_distributions.pdf`: Reference configuration performance distributions (12 stations, 18 Mbps BG, 25 ms deadline).
* `fig2_reference_paired_diffs.pdf`: Seed-by-seed paired performance differences relative to U-AFS across 40 seeds.
* `fig3_stress_n32.pdf`: High-density scalability stress distributions under 32 client stations.
* `fig4_load_6mbps.pdf`: Performance distributions under light background load (6 Mbps).
* `fig5_load_36mbps.pdf`: Performance distributions under severe background saturation (36 Mbps).
* `fig6_deadline_10ms.pdf`: Performance distributions under ultra-tight delay deadline ($D=10$ ms).
* `fig7_channel_bad_p02.pdf`: Performance distributions under unfavorable channel fading ($p_{\text{enter}}=0.20$).
* `fig8_bursty_traffic.pdf`: Performance distributions under bursty Pareto background arrivals.
* `fig9_rate_half.pdf`: Performance distributions under degraded physical layer transmission speeds.

### 02_edca_extension/
* `fig_e1_edca_reference_distributions.pdf`: IEEE 802.11e EDCA baseline comparison under reference configuration.
* `fig_e2_edca_reference_paired_diffs.pdf`: Paired per-seed differences between U-AFS and 802.11e EDCA.
* `fig_e4_edca_bad_channel_distributions.pdf`: EDCA baseline comparison under degraded channel fading.

### 03_tcp_extension/
* `fig_t1_tcp_reference_distributions.pdf`: Performance distributions under closed-loop AIMD TCP Reno dynamics.
* `fig_t2_tcp_reference_paired_diffs.pdf`: Paired performance differences relative to U-AFS under TCP traffic.

### 04_obss_extension/
* `fig_o1_obss_clean_distributions.pdf`: Multi-AP co-channel contention under clean channel baseline.
* `fig_o4_obss_40pct_distributions.pdf`: Multi-AP co-channel contention distributions under heavy 40% stolen airtime.
