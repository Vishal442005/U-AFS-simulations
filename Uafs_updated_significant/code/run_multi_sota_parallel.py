#!/usr/bin/env python3
"""
run_multi_sota_parallel.py
--------------------------
High-throughput parallelized multi-condition simulation campaign.
Leverages all 12 CPU cores via ProcessPoolExecutor.
"""

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import os
from pathlib import Path
import time
import pandas as pd

from schedulers import SchedulerConfig, Policy
from simulator import ModelConfig, make_workload, simulate

POLICIES = [
    "proposed",
    "lsdsf",
    "lyapunov",
    "exp_rule",
    "m_lwdf",
    "edf",
    "edca",
    "service_drr",
    "round_robin",
]

OUTPUT_DIR = Path("Uafs_updated_significant/results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def simulate_one(task):
    m_dict, s_dict, policy, seed, tag, extra_meta = task
    m_cfg = ModelConfig(**m_dict)
    s_cfg = SchedulerConfig(**s_dict)
    wl = make_workload(m_cfg, seed=seed)
    res = simulate(wl, policy, s_cfg)
    
    row = {
        "policy": policy,
        "seed": seed,
        "tag": tag,
        "stations": m_cfg.stations,
        "duration_s": m_cfg.duration_s,
        "bg_mbps": m_cfg.background_mbps,
        "deadline_ms": m_cfg.deadline_s * 1000.0,
        "bad_enter": m_cfg.bad_enter,
        "rt_miss_fraction": res["rt_miss_fraction"],
        "rt_p99_ms": res["rt_p99_ms"],
        "bg_goodput_mbps": res["bg_goodput_mbps"],
        "bg_delivery_fraction": res["bg_delivery_fraction"],
        "service_jain": res.get("service_jain", 0.0),
        "airtime_jain": res.get("airtime_jain", 0.0),
        "scheduler_us": res.get("scheduler_us_per_decision", 0.0),
    }
    row.update(extra_meta)
    return row

def run_batch_parallel(tasks, out_csv, max_workers=10):
    t0 = time.time()
    total = len(tasks)
    print(f"Executing {total} runs with {max_workers} workers -> {out_csv.name}...", flush=True)
    records = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(simulate_one, t) for t in tasks]
        done_count = 0
        for f in as_completed(futures):
            records.append(f.result())
            done_count += 1
            if done_count % 50 == 0 or done_count == total:
                elapsed = time.time() - t0
                print(f"  [{done_count}/{total}] completed ({elapsed:.1f}s, {done_count/elapsed:.1f} runs/s)", flush=True)

    df = pd.DataFrame(records)
    df.to_csv(out_csv, index=False)
    print(f"Successfully saved {len(df)} records to {out_csv}\n", flush=True)
    return df

def main():
    print("================================================================================", flush=True)
    print("      U-AFS HIGH-THROUGHPUT PARALLEL SIMULATION CAMPAIGN (10 WORKERS)          ", flush=True)
    print("================================================================================\n", flush=True)

    # 1. Reference Scenario (N=12, 18 Mbps BG, D=25 ms, 20 seeds)
    ref_tasks = []
    for seed in range(101, 121):
        m_cfg = ModelConfig(stations=12, duration_s=2.5, drain_s=0.3, background_mbps=18.0, deadline_s=0.025)
        s_cfg = SchedulerConfig(stations=12)
        for pol in POLICIES:
            ref_tasks.append((asdict(m_cfg), asdict(s_cfg), pol, seed, "reference", {"scenario": "reference"}))
    run_batch_parallel(ref_tasks, OUTPUT_DIR / "sota_reference_benchmark.csv")

    # 2. Station Density Scaling (N in {4, 8, 12, 16, 24, 32}, 10 seeds)
    scale_tasks = []
    for n in [4, 8, 12, 16, 24, 32]:
        for seed in range(201, 211):
            m_cfg = ModelConfig(stations=n, duration_s=2.0, drain_s=0.2, background_mbps=18.0, deadline_s=0.025)
            s_cfg = SchedulerConfig(stations=n)
            for pol in POLICIES:
                scale_tasks.append((asdict(m_cfg), asdict(s_cfg), pol, seed, f"stations_{n}", {"scenario": "station_scaling"}))
    run_batch_parallel(scale_tasks, OUTPUT_DIR / "station_density_scaling.csv")

    # 3. Traffic Mix Heterogeneity (80/20, 50/50, 20/80, 10 seeds)
    mix_tasks = []
    mix_configs = [
        ("RT_Heavy_80_20", 0.005, 6.0),
        ("Balanced_50_50", 0.010, 18.0),
        ("Bulk_Heavy_20_80", 0.025, 30.0),
    ]
    for mix_label, rt_per, bg_rate in mix_configs:
        for seed in range(301, 311):
            m_cfg = ModelConfig(stations=12, duration_s=2.0, drain_s=0.2, rt_period_s=rt_per, background_mbps=bg_rate, deadline_s=0.025)
            s_cfg = SchedulerConfig(stations=12)
            for pol in POLICIES:
                mix_tasks.append((asdict(m_cfg), asdict(s_cfg), pol, seed, mix_label, {"scenario": "traffic_mix", "traffic_mix": mix_label}))
    run_batch_parallel(mix_tasks, OUTPUT_DIR / "traffic_mix_heterogeneity.csv")

    # 4. Delay Deadline Tightness (D in {10, 15, 20, 25, 35, 50} ms, 10 seeds)
    deadline_tasks = []
    for d_ms in [10.0, 15.0, 20.0, 25.0, 35.0, 50.0]:
        for seed in range(401, 411):
            m_cfg = ModelConfig(stations=12, duration_s=2.0, drain_s=0.2, background_mbps=18.0, deadline_s=d_ms / 1000.0)
            s_cfg = SchedulerConfig(stations=12)
            for pol in POLICIES:
                deadline_tasks.append((asdict(m_cfg), asdict(s_cfg), pol, seed, f"deadline_{int(d_ms)}ms", {"scenario": "deadline_sweep"}))
    run_batch_parallel(deadline_tasks, OUTPUT_DIR / "deadline_tightness_sweep.csv")

    # 5. Channel Asymmetry & Fading (bad_enter in {0.0, 0.05, 0.10, 0.20}, 10 seeds)
    fading_tasks = []
    for p_enter in [0.0, 0.05, 0.10, 0.20]:
        for seed in range(501, 511):
            m_cfg = ModelConfig(stations=12, duration_s=2.0, drain_s=0.2, background_mbps=18.0, bad_enter=p_enter, deadline_s=0.025)
            s_cfg = SchedulerConfig(stations=12)
            for pol in POLICIES:
                fading_tasks.append((asdict(m_cfg), asdict(s_cfg), pol, seed, f"fading_p{p_enter}", {"scenario": "fading_sweep"}))
    run_batch_parallel(fading_tasks, OUTPUT_DIR / "channel_fading_asymmetry.csv")

    # 6. Operational Envelope 2D Grid (RT load x BG load)
    env_tasks = []
    rt_periods = [0.006, 0.010, 0.015, 0.020]
    bg_rates = [6.0, 14.0, 22.0, 32.0]
    for rt_p in rt_periods:
        for bg_r in bg_rates:
            for seed in range(601, 604):
                m_cfg = ModelConfig(stations=8, duration_s=2.0, drain_s=0.2, rt_period_s=rt_p, background_mbps=bg_r, deadline_s=0.025)
                s_cfg = SchedulerConfig(stations=8)
                for pol in ["proposed", "edf", "service_drr", "lyapunov"]:
                    env_tasks.append((asdict(m_cfg), asdict(s_cfg), pol, seed, f"grid_rt{rt_p}_bg{bg_r}", {
                        "scenario": "operational_envelope",
                        "rt_load_factor": round(0.010 / rt_p, 2),
                        "bg_load_mbps": bg_r
                    }))
    run_batch_parallel(env_tasks, OUTPUT_DIR / "operational_envelope_2d.csv")

    print("================================================================================", flush=True)
    print("ALL PARALLEL EXPERIMENTS COMPLETED SUCCESSFULLY!", flush=True)
    print("================================================================================", flush=True)

if __name__ == '__main__':
    main()
