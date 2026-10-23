# U-AFS: Urgency-Aware Fair Scheduling for Wi-Fi Networks

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![DOI](https://zenodo.org/badge/DOI/placeholder.svg)](https://zenodo.org/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

This repository contains the simulation framework, parameter auto-tuning algorithms, test suites, and empirical evaluation data for **U-AFS (Urgency-Aware Fair Scheduler)** in IEEE 802.11 wireless local area networks.

---

## Overview

Access point (AP) downlink scheduling must jointly serve deadline-sensitive real-time (RT) flows (e.g., cloud gaming, interactive video, industrial telemetry) and throughput-intensive best-effort background (BG) traffic without starving stations. Classical policies fail on at least one objective:
* **Round-Robin (RR):** Ignores deadlines (~99% miss rate under heavy load).
* **Earliest Deadline First (EDF):** Prioritizes deadlines but starves background traffic and degrades Jain's fairness.
* **Deficit Round-Robin (DRR):** Protects long-term service fairness but fails latency deadlines.
* **IEEE 802.11e EDCA:** Static Access Category prioritization that offers no intra-AC deadline or debt compensation.

**U-AFS** resolves this tension through a three-stage decision mechanism:
1. **Urgency Horizon ($H_u$):** Flags RT packets whose slack falls below an urgency threshold.
2. **Hybrid Urgency-Credit Scoring:** Prioritizes urgent packets while penalizing stations that have consumed excessive channel resources.
3. **Background Service-Debt Credit:** Maintains a background debt counter that guarantees background flows receive a bounded minimum share of channel time.

---

## Repository Structure

```
.
├── schedulers.py         # Scheduler implementations: U-AFS, EDCA, DRR, EDF, RR, and ablations
├── simulator.py          # Discrete-event wireless simulation engine with TCP Reno & OBSS models
├── autotuner.py          # Simultaneous Perturbation Stochastic Approximation (SPSA) tuner
├── ns3_bridge.py         # ns-3 MAC/PHY bridge & standalone CSMA/CA Bianchi contention model
├── run_all.py            # Comprehensive experiment orchestration suite
├── test_schedulers.py    # Unit tests for scheduling algorithms
├── test_simulator.py     # Unit tests for discrete-event engine
├── tables/               # Complete CSV/Markdown evaluation tables across all suites
│   ├── 01_main_evaluation/   # Core 16-configuration main study (4,480 runs)
│   ├── 02_edca_extension/    # IEEE 802.11e EDCA standard baseline comparison
│   ├── 03_tcp_extension/     # Closed-loop AIMD TCP Reno traffic dynamics
│   ├── 04_obss_extension/    # Overlapping BSS (OBSS) co-channel interference sweeps
│   └── 05_ns3_extension/     # ns-3 CSMA/CA MAC/PHY validation metrics
├── figures/              # High-resolution publication plots (PNG raster)
│   ├── 01_main_evaluation/   # Main sensitivity and paired improvement plots
│   ├── 02_edca_extension/    # EDCA comparative distributions
│   ├── 03_tcp_extension/     # TCP goodput and delay curves
│   └── 04_obss_extension/    # Interference airtime sweeps
├── .zenodo.json          # Zenodo metadata configuration for automatic DOI minting
└── CITATION.cff          # Machine-readable academic citation metadata
```

---

## Installation & Setup

Clone the repository and install requirements:
```bash
git clone https://github.com/Vishal442005/U-AFS-simulations.git
cd U-AFS-simulations
pip install numpy scipy matplotlib
```

Verify the installation by running the test suite:
```bash
python -m unittest test_schedulers test_simulator -v
```

---

## Reproducing Experiments

### 1. Main Evaluation Suite (Section 5)
Runs the full 16-configuration one-factor sensitivity analysis across all 7 policies and 40 random seeds:
```bash
python run_all.py --suite evaluation --seeds 40 --out evaluation_results
```

### 2. IEEE 802.11e EDCA Baseline (Section 6-A)
Compares U-AFS against strict-priority 802.11e EDCA across station counts and offered loads:
```bash
python run_all.py --suite edca --seeds 40 --out edca_results
```

### 3. Closed-Loop TCP Reno Background Dynamics (Section 6-C)
Tests whether the background service-debt mechanism causes TCP timeouts or congestion window collapse:
```bash
python run_all.py --suite tcp --seeds 40 --out tcp_results
```

### 4. Overlapping BSS (OBSS) Multi-AP Interference (Section 6-D)
Evaluates co-channel interference and medium contention from competing APs (sweeping airtime loss from 5% to 40%):
```bash
python run_all.py --suite obss --seeds 40 --out obss_results
```

### 5. SPSA Parameter Auto-Tuning (Section 6-B)
Runs adaptive gradient estimation to auto-tune U-AFS hyperparameters ($H_u, w_f, \alpha_{bg}, Q$):
```bash
python autotuner.py --n-iter 200 --train-seeds 20 --held-seeds 20 --out tuning_results
```

### 6. ns-3 MAC/PHY Bridge (Section 6-E)
Validates scheduling decisions against full CSMA/CA backoff, DCF inter-frame spacing, and physical-layer capture effects:
```bash
python ns3_bridge.py --mode standalone --policy proposed --seeds 5 --out ns3_results
```

---

## Citation

If you use U-AFS in your research, please cite:

```bibtex
@software{chandel2026uafs,
  author       = {Vishal Chandel},
  title        = {U-AFS: Urgency-Aware Fair Scheduler for Mixed Real-Time and Background Traffic in Wi-Fi Networks},
  year         = {2026},
  publisher    = {GitHub},
  journal      = {GitHub repository},
  howpublished = {\url{https://github.com/Vishal442005/U-AFS-simulations}}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
