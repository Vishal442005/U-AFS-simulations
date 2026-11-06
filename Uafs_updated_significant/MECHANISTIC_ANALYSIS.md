# Mechanistic Analysis of Performance Curves & Phenomena
**Document Class:** In-Depth Physical & Queueing Dissection of Experimental Trends  
**Component of:** `Uafs_updated_significant` Framework  
**Author:** Vishal Chandel  
**Date:** November 6, 2026  

---

## 1. Scope & Objective

A primary critique of the editorial decision was:
> *"Many of the curves are only commented without sufficient explanatory details on the reason for their trend... there is a lack of explanatory details on the reason for their trend."*

This document provides a thorough, causal, and mathematically grounded physical commentary for every major empirical trend observed across the experimental evaluation. It explicitly identifies:
1. **Inflection / Knee Points:** The exact parameter values where performance curves change derivative.
2. **Underlying Protocol & Queue Dynamics:** Contention window backoffs, Head-of-Line (HoL) blocking, credit drift, and debt starvation guards.
3. **Comparative Contrasts:** Why competing algorithms (EDF, EDCA, LSDSF, Lyapunov, Service-DRR, M-LWDF, EXP-Rule) behave differently at each operating regime.

---

## 2. Detailed Curve-by-Curve Mechanistic Dissections

### A. Figure 1: Reference Performance Distributions Across SOTA Schemes
* **Observations:**
  - Real-Time Deadline Miss: U-AFS achieves **18.41%**, compared to **21.8%** (LSDSF), **23.1%** (Lyapunov), **22.5%** (EXP-Rule), **33.24%** (EDF), and **64.93%** (Service-DRR).
  - Background Bulk Goodput: U-AFS delivers **11.80 Mbps**, while EDF drops to **8.90 Mbps** and Service-DRR achieves **14.78 Mbps**.
  - Service Fairness: U-AFS achieves $J_S = 0.998$, compared to $0.840$ (EDF) and $0.798$ (Round-Robin).
* **Causal Mechanism:**
  - *Why EDF drops bulk goodput by 2.90 Mbps (-24.6%):* EDF is purely deadline-driven. In a saturated WLAN, real-time packets arrive at high frequency. Under channel retries, EDF monopolizes the AP downlink transmitter with real-time packets. Background bulk packets wait indefinitely in per-station FIFO buffers, suffering severe buffer bloat and queue drop.
  - *Why Service-DRR misses 64.93% deadlines:* DRR rotates quantums ($Q = 1.0\text{ ms}$) in round-robin fashion. While this guarantees throughput fairness, a real-time frame with a $25\text{ ms}$ deadline often arrives just after its station's deficit quantum is exhausted. It must wait for all other $N-1 = 11$ stations to complete their service turns before being eligible for transmission, accumulating fatal Head-of-Line waiting delay that exceeds the deadline.
  - *Why U-AFS solves both simultaneously:* U-AFS maintains two independent state metrics: the deficit debt counter $D_{bg}$ and the per-station credit vector $C_s(t)$. Because Stage 1 fires whenever $D_{bg} \ge \alpha_{bg} \tau_{bg}$, background traffic receives a guaranteed airtime slice, while Stage 2 normalizes deadline slack $\tau_i(t) / H_u$ so that only urgent packets pre-empt fairness.

---

### B. Figure 2: Station Density Scaling ($N = 4 \to 32$)
* **Observations:**
  - Miss fraction remains relatively low and flat from $N=4$ ($13.95\%$) to $N=12$ ($18.41\%$), rises gently to $N=16$ ($20.44\%$), and then sharply accelerates to **36.48%** at $N=32$.
  - EDF degrades steeply from $26.16\%$ ($N=4$) to $35.62\%$ ($N=16$) and **56.16%** at $N=32$.
* **Causal Mechanism & The Contention Knee at $N=16$:**
  - *Contention Window Exhaustion:* In IEEE 802.11 CSMA/CA, the collision probability on a channel with $N$ active stations is governed by Bianchi's relation:
    $$P_{coll} = 1 - (1 - \tau)^N$$
    where $\tau$ is the transmission probability per slot. For $N \le 16$, the standard contention window ($CW_{min} = 15, CW_{max} = 1023$) provides sufficient slot spacing to keep packet collision probability below $P_{coll} \approx 0.18$.
  - *The Transition at $N > 16$:* Beyond $N=16$, the number of contending stations exceeds the default slot capacity ($CW_{min} = 15$). Collision rates exceed $32\%$, causing repeated exponential backoffs and frequent retry limit hits ($K = 4$).
  - *Why U-AFS scales superiorly to $N=32$:* When multiple stations contend simultaneously, EDF experiences catastrophic HoL queue freezing—retrying doomed packets until deadline expiry. U-AFS's Stage-3 proactively computes $\tau_i(t) = D_i - t - \hat{S}_i$. If $\tau_i(t) < 0$, U-AFS drops the packet *before* wasting physical channel airtime, preserving channel capacity for packets that can still be salvaged.

---

### C. Figure 3: Traffic Mix Asymmetry (RT-Heavy vs. Bulk-Heavy)
* **Observations:**
  - Under RT-Heavy traffic (80% RT / 20% Bulk), U-AFS achieves **12.4%** miss rate and **5.9 Mbps** goodput.
  - Under Bulk-Heavy traffic (20% RT / 80% Bulk), U-AFS achieves **4.8%** miss rate and **17.2 Mbps** goodput.
* **Causal Mechanism:**
  - *Queueing Arrival Rates:* Under RT-heavy traffic, the arrival intensity $\lambda_{rt}$ is high. The urgency pool $\mathcal{U}$ is non-empty in almost every scheduling epoch ($|\mathcal{U}| \ge 1$). As a result, the scheduler operates predominantly in Stage 2.
  - *Credit Distribution Dynamics:* Because the background debt counter increments as $D_{bg} \leftarrow D_{bg} + \alpha_{bg} S_i$, higher real-time traffic volume rapidly drives $D_{bg}$ above its threshold, guaranteeing that the small volume of bulk traffic is dispatched without starvation.
  - Under bulk-heavy traffic, real-time packet arrivals are sparse ($\lambda_{rt}$ is low). When a real-time packet arrives, it finds the urgency pool empty of competitors, immediately wins Stage 2 arbitration, and is dispatched with minimal delay (miss rate drops to $4.8\%$).

---

### D. Figure 4: Delay Deadline Tightness ($D = 10 \to 50$ ms)
* **Observations:**
  - For $D \ge 35\text{ ms}$, real-time miss rate is virtually zero ($<1.8\%$) across all schemes except Round-Robin.
  - A dramatic inflection (knee point) occurs between $D = 20\text{ ms}$ and $D = 10\text{ ms}$, where miss rate climbs to **44.88%** at $D = 10\text{ ms}$.
* **Causal Mechanism & The Physical Transmission Bound:**
  - *Nominal Frame vs. Tail Transmission Time:* A single nominal frame transmission requires $S^{nom} \approx 0.266\text{ ms}$. However, the physical delay experienced by a packet is a random variable:
    $$T_{service} = \sum_{k=1}^M \left( T_{DIFS} + \text{Backoff}_k + T_{frame} + T_{SIFS} + T_{ACK} \right)$$
    Under channel fading and retry limits ($M \le 4$), empirical measurement shows the 99th-percentile service time is $T_{p99} \approx 18.96\text{ ms}$.
  - *The Mathematical Delay Bound:* When the relative deadline is configured to $D = 10\text{ ms}$, it falls *strictly below* the physical 99th-percentile transmission delay distribution ($D < T_{p99}$). At this point, packets experiencing 2 or more retries inevitably miss their deadline regardless of scheduler intelligence.
  - *U-AFS Advantage:* Rather than fruitlessly transmitting frames whose slack has already expired ($\tau_i(t) < 0$), U-AFS purges them immediately, freeing up the channel to serve urgent frames that still have positive slack ($\tau_i(t) \in [0, H_u]$).

---

### E. Figure 5: 2D Operational Feasibility Heatmap
* **Observations:**
  - Visualizes the 2D performance contour over normalized real-time load ($\lambda_{rt} / C_{rt}$) vs. background load ($\lambda_{bg}$).
  - A distinct high-gain ridge (+14 to +18 percentage point advantage over EDF) is visible along the diagonal where $\rho_{total} \in [0.65, 0.95]$.
* **Causal Mechanism:**
  - Along this diagonal, channel resources are scarce enough that naive schedulers fail, yet feasible enough that intelligent urgency-credit arbitration can deliver near-optimal scheduling.
  - When $\lambda_{rt}$ and $\lambda_{bg}$ are both high, the dual-bucket decoupling of starvation debt and urgency slack prevents either traffic class from cannibalizing the other.

---

### F. Figure 6: Multi-Metric Pareto Frontier
* **Observations:**
  - U-AFS sits at the absolute top-left extreme of the Pareto trade-off curve (lowest miss fraction at 18.41%, high goodput at 11.80 Mbps).
  - Baselines like EDF sacrifice goodput (8.90 Mbps) for moderate miss reduction (33.24%), while Service-DRR sacrifices deadlines (64.93% miss) for throughput (14.78 Mbps).
* **Causal Mechanism:**
  - U-AFS achieves Pareto superiority because it does not optimize one metric at the expense of the other; its multi-stage decision pipeline separates orthogonal objectives into distinct decision gates (Stage 1 = Bulk Starvation Invariant, Stage 2 = Urgency/Fairness Pareto Balance, Stage 3 = Dead-Packet Airtime Recovery).
