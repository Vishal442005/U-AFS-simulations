# U-AFS: Updated & Significant Results Framework (`Uafs_updated_significant`)
**Author:** Vishal Chandel  
**Affiliation:** Department of Electronics and Communication Engineering, Jawaharlal Nehru Government Engineering College (JNGEC), Sundernagar, India  
**Date:** November 6, 2026  
**License:** MIT Open Source License  

---

## 1. Directory Overview & Organization

This directory provides the complete, self-contained, and audited evaluation framework developed to address the editorial review critiques from *IEEE Transactions* and *Elsevier Computer Networks*. 

It contains expanded empirical campaigns, deep physical/queueing analyses, operational feasibility syntheses, and newly benchmarked state-of-the-art literature schedulers.

```
Uafs_updated_significant/
├── README.md                           # Master manifest, architecture summary, and empirical audit
├── OPERATIONAL_ENVELOPE.md             # Synthesis: Feasibility envelope, boundary conditions, sweet spot
├── MECHANISTIC_ANALYSIS.md             # Causal analysis: Causal queueing explanations, knee points, and trends
│
├── code/                               # Clean, reproducible simulation scripts & test suites
│   ├── schedulers.py                   # 9 schedulers: U-AFS, LSDSF, Lyapunov, M-LWDF, EXP-Rule, EDF, EDCA, DRR, RR
│   ├── simulator.py                    # Discrete-event MAC/PHY simulator with fading & contention
│   ├── run_multi_sota_parallel.py      # High-throughput 12-core parallel simulation engine
│   ├── generate_significant_tables.py  # Automated markdown/CSV tabular synthesizer
│   ├── render_significant_plots.py     # Publication-grade vector PDF + 300 DPI PNG generator
│   ├── test_schedulers.py              # Unit test suite verifying scheduling contracts (28 tests)
│   └── test_simulator.py               # Unit test suite verifying simulator conservation laws (5 tests)
│
├── results/                            # Raw empirical CSV datasets (2,082 Monte Carlo runs)
│   ├── sota_reference_benchmark.csv    # 180 runs (20 seeds x 9 policies) under reference setup
│   ├── station_density_scaling.csv     # 540 runs (N in {4, 8, 12, 16, 24, 32} across all policies)
│   ├── traffic_mix_heterogeneity.csv   # 270 runs (80/20, 50/50, 20/80 mixes)
│   ├── deadline_tightness_sweep.csv    # 540 runs (D in {10, 15, 20, 25, 35, 50} ms)
│   ├── channel_fading_asymmetry.csv    # 360 runs (Gilbert-Elliott bad-entry p in {0.0, 0.05, 0.10, 0.20})
│   └── operational_envelope_2d.csv     # 192 runs (2D grid of real-time load vs background load)
│
├── tables/                             # Publication-ready formatted tables (CSV + Markdown)
│   ├── Table_SOTA_Reference_Summary.csv & .md
│   ├── Table_Station_Scaling_Extended.csv & .md
│   ├── Table_Traffic_Mix_Sensitivity.csv & .md
│   ├── Table_Deadline_Tightness_Matrix.csv & .md
│   ├── Table_Fading_Asymmetry_Analysis.csv & .md
│   └── Table_Operational_Regimes_Synthesis.csv & .md
│
└── figures/                            # High-resolution vector PDFs and 300 DPI PNGs
    ├── fig1_sota_reference_distributions.pdf / .png
    ├── fig2_station_density_scaling.pdf / .png
    ├── fig3_traffic_mix_tradeoffs.pdf / .png
    ├── fig4_deadline_sensitivity_breakdown.pdf / .png
    ├── fig5_operational_envelope_heatmap.pdf / .png
    └── fig6_multimetric_pareto_frontier.pdf / .png
```

---

## 2. Key Scientific Findings & SOTA Comparison

Under the Reference Scenario ($N=12$ client stations, $18\text{ Mbps}$ background offered load, $D=25\text{ ms}$ relative deadline, 20 independent random seeds):

| Scheduler Policy | Reference Paper / Provenance | Real-Time Miss (%) | 99th-Percentile Delay (ms) | Background Goodput (Mbps) | Service Jain's Index |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **U-AFS (Proposed)** | **This Work** | **10.28%** | **19.08 ms** | **11.30 Mbps** | **0.998** |
| **LSDSF** | Jain et al. (*ACM MobiHoc 2024*) | 17.59% | 24.86 ms | 11.76 Mbps | 0.847 |
| **EXP-Rule** | Shakkottai et al. (*IEEE Trans. Inf. Theory*) | 16.01% | 3.87 ms | 12.02 Mbps | 0.865 |
| **Lyapunov Drift-Penalty** | Zhang et al. (*IEEE/ACM ToN 2024*) | 25.05% | 15.65 ms | 12.41 Mbps | 0.851 |
| **M-LWDF** | Andrews et al. (*IEEE Comm. Mag.*) | 84.41% | 24.94 ms | 15.32 Mbps | 0.885 |
| **Earliest Deadline First (EDF)** | Liu & Layland (*Classical*) | 15.54% | 6.34 ms | 7.84 Mbps | 0.847 |
| **IEEE 802.11e EDCA** | IEEE 802.11e Standard AC Queues | 15.54% | 6.34 ms | 7.84 Mbps | 0.847 |
| **Service-DRR** | Shreedhar & Varghese (*IEEE/ACM ToN*) | 63.71% | 24.77 ms | 14.78 Mbps | 0.995 |
| **Round-Robin** | Classical Fair Queuing | 98.64% | 24.94 ms | 13.19 Mbps | 0.798 |

---

## 3. How This Addresses the Editorial Critique

1. **Expands Baseline Comparison:** Benchmarks U-AFS against modern literature schedulers (LSDSF, Lyapunov, EXP-Rule, M-LWDF) across diverse multi-condition sweeps (scaling $N \in [4, 32]$, mix skews, deadline tightness, channel fading).
2. **Provides Causal Explanations:** Every curve is dissected into physical queueing drivers (HoL blocking, contention window backoffs, retry exhaustion) in `MECHANISTIC_ANALYSIS.md`.
3. **Formalizes the Operational Envelope:** Synthesizes where U-AFS excels (congested mixed traffic, heterogeneous SNRs), where it ties (light loads $< 0.45$), and where it encounters deliberate trade-offs in `OPERATIONAL_ENVELOPE.md`.
4. **Reproducibility Guarantee:** All 2,082 simulation records and plotting routines are cleanly organized and executable via `python code/run_multi_sota_parallel.py`.
