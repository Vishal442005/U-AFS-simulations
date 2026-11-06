# Synthesis: Operational Envelope & Boundary Conditions of U-AFS
**Document Class:** Archival Systems Synthesis & Performance Generality Analysis  
**Component of:** `Uafs_updated_significant` Framework  
**Author:** Vishal Chandel  
**Date:** November 6, 2026  

---

## 1. Executive Motivation: Why Schedulers Require Operational Boundaries

In peer-reviewed wireless literature (e.g., *IEEE Transactions on Mobile Computing*, *IEEE/ACM Transactions on Networking*), claiming that a single scheduling policy uniformly dominates across all operational environments is scientifically unsound. Every MAC/PHY scheduling arbiter embodies fundamental trade-offs governed by channel capacity, traffic burstiness, and queueing constraints.

This document establishes the **Operational Feasibility Envelope** of **U-AFS (Urgency-Aware Fair Scheduling)**. It explicitly delineates:
1. **The Primary Dominance Zone (The "Sweet Spot"):** Where U-AFS achieves its maximum competitive margin over SOTA baselines.
2. **The Parity Zone:** Where U-AFS performs identically to simpler, classical schedulers (and where U-AFS overhead is unnecessary).
3. **The Boundary Trade-off Zone:** Where U-AFS incurs deliberate, controlled trade-offs (e.g., minor real-time priority inversion) to preserve foundational system invariants such as background starvation-freedom.
4. **Degenerate Edge Cases:** How U-AFS gracefully collapses into classical queueing disciplines when specific traffic classes are absent.

---

## 2. Quantitative Operational Envelope Matrix

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            U-AFS OPERATIONAL REGIME TAXONOMY                                           │
├────────────────────┬────────────────────┬─────────────────────────────┬────────────────────────────────────────────────┤
│ Operating Regime   │ Boundary Parameter │ Empirical Performance       │ Governing Mechanism & System Trade-Offs        │
│                    │ Conditions         │ Relative to SOTA Baselines  │                                                │
├────────────────────┼────────────────────┼─────────────────────────────┼────────────────────────────────────────────────┤
│ 1. Light Load      │ Offered intensity  │ Parity with EDF & EDCA      │ Delay slack is ample (tau >> Hu). The Stage-2  │
│    (Under-saturated)│ rho < 0.45         │ RT Miss: < 1.0% across all  │ urgency window is unexercised. Frames dispatch │
│                    │ Backlog: < 2 pkts  │ BG Goodput: 100% offered    │ in arrival/slack order. Advanced arbitration   │
│                    │                    │ Jain's Equity: > 0.99       │ yields negligible gain; basic FIFO suffices.   │
├────────────────────┼────────────────────┼─────────────────────────────┼────────────────────────────────────────────────┤
│ 2. Moderately      │ Offered intensity  │ DOMINANT ADVANTAGE          │ Sweet Spot: Real-time packets compete for      │
│    Congested Mixed │ rho in [0.60, 0.95]│ RT Miss: 18.4% vs 33.2%(EDF)│ channel airtime. Stage-2 slack normalization   │
│    Traffic         │ BG Load: 12-24 Mbps│ BG Goodput: +32.6% over EDF │ prevents deadline expiration; Stage-1 debt     │
│    (Sweet Spot)    │ Stations: N=8..24  │ Jain's Equity: 0.998 vs 0.84│ counter Delta_bg deterministically prevents    │
│                    │ Fading: p in [0,0.1│ Miss drop: -14.8 pp         │ bulk starvation; credit balancing eliminates   │
│                    │                    │ (p = 1.22e-9, dz = 16.4)    │ the 802.11 anomalous station throughput trap.  │
├────────────────────┼────────────────────┼─────────────────────────────┼────────────────────────────────────────────────┤
│ 3. Extreme Channel │ Offered intensity  │ Controlled Trade-off        │ Channel is over-saturated. Stage-1 background  │
│    Starvation &    │ rho > 1.20         │ RT Miss: 36.5% vs 56.2%(EDF)│ debt triggers every K=8 frames to honor bulk   │
│    Over-saturation │ OBSS Medium Steal  │ BG Goodput: 4.97 Mbps (UAFS)│ throughput bounds. This introduces small       │
│                    │ gamma >= 0.40      │ vs 3.59 Mbps (EDF)          │ priority inversions against marginal RT pkts;  │
│                    │ Stations: N=32     │                             │ pure strict priority achieves fewer RT misses  │
│                    │                    │                             │ (+3.5 pp), but completely starves bulk (0 Mbps)│
├────────────────────┼────────────────────┼─────────────────────────────┼────────────────────────────────────────────────┤
│ 4. Pure Real-Time  │ Background load:   │ Identical to Pruned-EDF     │ With lambda_bg = 0, background queues are      │
│    Telemetry Only  │ lambda_bg = 0      │ with Credit Tie-Breaking    │ empty. Debt Delta_bg remains 0; Stage 1 never  │
│    (No Bulk)       │ RT flows only      │ RT Miss: 12.1% (N=12)       │ fires. Scheduler degenerates into a pure fair  │
│                    │                    │                             │ Earliest-Deadline-First dispatch arbiter.      │
├────────────────────┼────────────────────┼─────────────────────────────┼────────────────────────────────────────────────┤
│ 5. Pure Bulk       │ Real-time load:    │ Identical to Service-DRR    │ With lambda_rt = 0, urgency pool U is empty.   │
│    Elastic Only    │ lambda_rt = 0      │ BG Goodput: 14.8 Mbps       │ Scheduler dispatches entirely via Stage-1 and   │
│    (No Deadlines)  │ Bulk TCP/UDP only  │ Jain's Equity: 0.998        │ credit balance, matching Deficit Round Robin.   │
└────────────────────┴────────────────────┴─────────────────────────────┴────────────────────────────────────────────────┘
```

---

## 3. Deep Architectural Dynamics Across Regimes

### A. Regime 1: Under-Saturated Channels ($\rho < 0.45$)
* **Queue Dynamics:** The average queue depth across all $N$ client station FIFOs is $\le 1.2$ frames. Inter-arrival intervals exceed the physical 802.11 frame transmission duration ($T_{frame} \approx 0.266\text{ ms}$).
* **Why Baselines Tie:** Head-of-line delay slack satisfies $\tau_i(t) = D_i - t - \hat{S}_i \gg H_u = 10\text{ ms}$. Because no packets fall into the critical urgency window $[0, H_u]$, the scheduler falls back to earliest-deadline FIFO ordering. Every scheduler (EDF, EDCA, LSDSF, U-AFS) delivers packets well before expiration.
* **Archival Guidance:** In sparse IoT or ultra-low-load environments, deploying complex multi-stage scheduling is unnecessary; lightweight FIFO queues suffice.

### B. Regime 2: The Congested Mixed-Traffic Sweet Spot ($\rho \in [0.60, 0.95]$)
* **Queue Dynamics:** Multiple per-station queues are simultaneously backlogged. Real-time packets and bulk elastic transfers contend for every transmission epoch.
* **Why SOTA Baselines Fail:**
  1. *Pure EDF:* Suffers catastrophic head-of-line blocking. When channel fading induces retries, EDF stubbornly attempts failing packets until deadline expiration, completely starving background bulk flows (Goodput drops to $8.90\text{ Mbps}$, Jain drops to $0.840$).
  2. *Service-DRR & Round-Robin:* Focus solely on throughput/airtime equity. They rotate rounds blindly, ignoring packet delay deadlines. Real-time packets expire while waiting for round completion (Miss rate escalates to $64.93\%$ in DRR, $99.40\%$ in RR).
  3. *IEEE 802.11e EDCA:* Static Access Category (AC_VO vs. AC_BE) priorities lack intra-class fairness. High-rate video streams monopolize the high-priority AC queue, starving other stations.
* **Why U-AFS Dominates:**
  - **Stage-1:** Brounds background starvation by enforcing $D_{bg} < \alpha_{bg} \tau_{bg} \approx 0.385\text{ ms}$.
  - **Stage-2:** Normalizes slack by urgency horizon $H_u$ and offsets it by service credit $C_s(t)$, balancing urgency against inter-station airtime equity.
  - **Stage-3:** Proactively prunes predicted-expired frames ($\tau_i(t) < 0$), preventing wasteful PHY contention.

### C. Regime 3: Severe Over-Saturation & External Starvation ($\rho > 1.20$, $\gamma \ge 0.40$)
* **Queue Dynamics:** The AP MAC buffer is completely backlogged. External co-channel interference (OBSS airtime stealing) restricts available medium access time.
* **The Inherent Trade-Off:** 
  - To prevent background TCP connections from suffering RTO timeouts (which would collapse TCP congestion windows to 1 MSS), U-AFS's Stage-1 guard fires every $K=8$ frames.
  - This intentional airtime reservation guarantees bulk traffic receives $4.97\text{ Mbps}$ goodput, but temporarily delays borderline real-time frames, resulting in an RT miss rate of $36.48\%$ at $N=32$.
  - A ruthless strict-priority scheduler that starves background traffic entirely could achieve an RT miss rate of $32.9\%$, but reduces background goodput to $0.0\text{ Mbps}$. U-AFS deliberately chooses balanced utility over single-metric extremism.

---

## 4. Parameter Sensitivity & Tuning Guidelines

| Parameter | Default Value | Tuning Direction & System Impact | Recommended Operational Setting |
| :--- | :--- | :--- | :--- |
| **Urgency Horizon $H_u$** | $10\text{ ms}$ | Increasing expands the set of urgent candidates (more fairness); decreasing prioritizes only critically urgent frames (tighter deadline focus). | Static: $H_u \in [10, 15]\text{ ms}$. Dynamic: Deploy online D-SPSA autotuner, which scales $H_u(t)$ up to $24\text{ ms}$ during heavy bursts. |
| **Fairness Weight $w_f$** | $0.20$ | Higher values enforce strict throughput parity at the cost of slight deadline misses; lower values favor timeliness over fairness. | Set $w_f \in [0.15, 0.25]$ for mixed enterprise WLANs; set $w_f = 0.05$ in mission-critical industrial telemetry. |
| **Background Share $\alpha_{bg}$** | $0.20$ | Direct knob governing minimum bulk bandwidth fraction ($20\%$). | Set $\alpha_{bg} = 0.20$ for balanced networks; decrease to $\alpha_{bg} = 0.05$ if real-time flows carry human safety constraints. |
| **Deficit Quantum $Q$** | $1.0\text{ ms}$ | Governs granularity of credit accumulation. Larger quantums reduce switching overhead; smaller quantums improve interleaving. | Standardize to $Q \in [0.8, 1.2]\text{ ms}$, matching the duration of 2–3 maximum-length 802.11 aggregation frames (A-MPDU). |
