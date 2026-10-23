#!/usr/bin/env python3
"""
Run scheduling experiments and generate statistics, plots, and tables.

Default:
    40 independent seeds per configuration
    all seven scheduling policies

Examples:
    python3 run_all.py --suite smoke --seeds 2 --duration 1 --out smoke
    python3 run_all.py --suite evaluation --out evaluation
    python3 run_all.py --suite evaluation --out evaluation --resume
    python3 run_all.py --suite evaluation --out evaluation --analyse-only

This evaluates a simplified network model, not a standards-compliant
Wi-Fi MAC/PHY implementation.
"""

import argparse
from dataclasses import asdict, replace
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.stats import rankdata, wilcoxon

from schedulers import POLICY_NAMES, SchedulerConfig
from simulator import ModelConfig, make_workload, simulate


POLICIES = list(POLICY_NAMES)

# Direction: +1 means larger is better; -1 means smaller is better.
METRICS = {
    "rt_miss_fraction": ("Deadline-miss fraction", -1),
    "rt_p99_ms": ("Received RT p99 delay (ms)", -1),
    "bg_goodput_mbps": ("Background goodput (Mbps)", 1),
    "bg_delivery_fraction": ("Background packet delivery fraction", 1),
    "bg_p95_delay_ms": ("Delivered BG p95 delay (ms)", -1),
    "service_jain": ("Service-time Jain fairness", 1),
    "airtime_jain": ("Modeled airtime Jain fairness", 1),
}

DESCRIPTIVE = {
    **{key: label for key, (label, _) in METRICS.items()},
    "mean_attempts": "Mean attempts per completed transmission",
    "scheduler_us_per_decision": "Measured scheduler microseconds",
}

COLORS = {
    "round_robin": "#E69F00",
    "edf": "#D55E00",
    "service_drr": "#009E73",
    "proposed": "#0072B2",
    "no_urgency": "#56B4E9",
    "no_fairness": "#CC79A7",
    "no_retry_estimate": "#777777",
    "edca": "#F0E442",          # IEEE 802.11e EDCA baseline (Extension 1)
}


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--suite",
        choices=[
            "smoke", "tuning", "evaluation", "sensitivity",
            "edca",      # Extension 1: IEEE 802.11e EDCA comparison
            "tcp",       # Extension 3: TCP background traffic
            "obss",      # Extension 4+5: OBSS / multi-AP contention
        ],
        default="evaluation",
    )
    parser.add_argument("--seeds", type=int, default=40)
    parser.add_argument("--first-seed", type=int)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--drain", type=float, default=1.0)
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--analysis-seed", type=int, default=314159)

    parser.add_argument("--reservation", type=float, default=0.20)
    parser.add_argument("--urgency-ms", type=float, default=10.0)
    parser.add_argument("--fairness-weight", type=float, default=0.25)
    parser.add_argument("--alpha", type=float, default=0.20)
    parser.add_argument("--quantum-ms", type=float, default=1.0)

    parser.add_argument("--out", default="results")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--analyse-only", action="store_true")
    parser.add_argument("--packet-logs", action="store_true")

    args = parser.parse_args()

    if args.seeds < 2:
        parser.error("--seeds must be at least 2.")
    if args.bootstrap < 1000:
        parser.error("--bootstrap must be at least 1000.")
    if args.analysis_seed < 0:
        parser.error("--analysis-seed must be non-negative.")
    if (
        not args.out
        or Path(args.out).name != args.out
        or args.out in {".", ".."}
    ):
        parser.error("--out must be a folder name, not a path.")

    if args.first_seed is None:
        args.first_seed = {
            "smoke": 1,
            "tuning": 1,
            "evaluation": 1001,
            "sensitivity": 2001,
            "edca": 3001,    # Extension 1: EDCA comparison seeds
            "tcp": 4001,     # Extension 3: TCP background seeds
            "obss": 5001,    # Extension 4+5: OBSS/multi-AP seeds
        }[args.suite]

    if args.first_seed < 0:
        parser.error("--first-seed must be non-negative.")

    return args


def build_cases(args):
    model = ModelConfig(
        duration_s=args.duration,
        drain_s=args.drain,
        stations=12,
        background_mbps=18.0,
        deadline_s=0.025,
    )

    scheduler = SchedulerConfig(
        stations=model.stations,
        background_share=args.reservation,
        urgency_horizon_s=args.urgency_ms / 1000.0,
        fairness_weight=args.fairness_weight,
        estimator_alpha=args.alpha,
        quantum_s=args.quantum_ms / 1000.0,
    )

    cases = []

    def add(name, model_changes=None, scheduler_changes=None):
        model_case = replace(model, **(model_changes or {}))
        scheduler_case = replace(
            scheduler,
            stations=model_case.stations,
            **(scheduler_changes or {}),
        )
        cases.append((name, model_case, scheduler_case))

    if args.suite == "smoke":
        add("smoke", {"stations": 3, "background_mbps": 2.0})
        return cases

    if args.suite == "tuning":
        for share, urgency in itertools.product(
            [0.10, 0.20, 0.30],
            [0.005, 0.010, 0.020],
        ):
            add(
                f"tune_share{share:g}_urgency{urgency:g}",
                {
                    "stations": 8,
                    "background_mbps": 10.0,
                    "deadline_s": 0.020,
                },
                {
                    "background_share": share,
                    "urgency_horizon_s": urgency,
                },
            )
        return cases

    add("reference")

    if args.suite == "evaluation":
        variations = {
            "stations": [4, 16, 32],
            "background_mbps": [6.0, 24.0, 36.0],
            "deadline_s": [0.010, 0.040, 0.080],
            "bad_enter": [0.20],
            "rt_period_s": [0.005, 0.020],
        }

        for parameter, values in variations.items():
            for value in values:
                add(f"{parameter}_{value:g}", {parameter: value})

        add("bursty_background", {"background_bursty": True})

        for scale in [0.5, 2.0]:
            add(
                f"rate_scale_{scale:g}",
                {
                    "rates_mbps": tuple(
                        rate * scale for rate in model.rates_mbps
                    )
                },
            )

    elif args.suite == "sensitivity":
        variations = {
            "background_share": [0.0, 0.10, 0.30, 0.40],
            "urgency_horizon_s": [0.0025, 0.005, 0.020],
            "fairness_weight": [0.0, 0.125, 0.50, 1.0],
            "estimator_alpha": [0.05, 0.50, 1.0],
            "quantum_s": [0.0005, 0.002, 0.004],
        }

        for parameter, values in variations.items():
            for value in values:
                add(
                    f"{parameter}_{value:g}",
                    scheduler_changes={parameter: value},
                )

        for parameter, values in {
            "queue_limit": [64, 1024],
            "max_attempts": [1, 7],
        }.items():
            for value in values:
                add(
                    f"{parameter}_{value}",
                    model_changes={parameter: value},
                )

    # ------------------------------------------------------------------
    # Extension 1 — IEEE 802.11e EDCA focused comparison
    # Mirrors the reference case but adds tight/loose deadline and
    # high-load conditions most likely to expose EDCA's lack of fairness.
    # ------------------------------------------------------------------
    elif args.suite == "edca":
        add("edca_reference")

        for bg_load in [6.0, 18.0, 30.0]:
            add(f"edca_bgload_{bg_load:g}", {"background_mbps": bg_load})

        for n_sta in [4, 8, 16]:
            add(f"edca_stations_{n_sta}", {"stations": n_sta})

        add("edca_bursty",    {"background_bursty": True})
        add("edca_tight",     {"deadline_s": 0.010})
        add("edca_loose",     {"deadline_s": 0.050})
        add("edca_bad_chan",  {"bad_enter": 0.20})

    # ------------------------------------------------------------------
    # Extension 3 — TCP background coexistence
    # Tests whether U-AFS's background-debt heuristic triggers TCP RTO
    # and collapse when background traffic has congestion-window dynamics.
    # ModelConfig.tcp_background (added in simulator.py Batch B) controls
    # whether the workload generator uses AIMD-shaped arrivals.
    # ------------------------------------------------------------------
    elif args.suite == "tcp":
        # UDP baseline for direct comparison (no TCP dynamics)
        add("tcp_udp_baseline", {
            "stations": 8,
            "background_mbps": 10.0,
            "deadline_s": 0.020,
        })
        # TCP with same load
        add("tcp_reference", {
            "stations": 8,
            "background_mbps": 10.0,
            "deadline_s": 0.020,
            "tcp_background": True,
        })
        # Sweep background load under TCP
        for bg_load in [5.0, 10.0, 15.0, 20.0]:
            add(f"tcp_bgload_{bg_load:g}", {
                "stations": 8,
                "background_mbps": bg_load,
                "deadline_s": 0.020,
                "tcp_background": True,
            })
        # Bursty TCP (slow-start bursts)
        add("tcp_bursty", {
            "stations": 8,
            "background_mbps": 10.0,
            "deadline_s": 0.020,
            "tcp_background": True,
            "background_bursty": True,
        })
        # Tight RT deadline — worst case for RTO-induced head-of-line blocking
        add("tcp_tight_deadline", {
            "stations": 8,
            "background_mbps": 10.0,
            "deadline_s": 0.010,
            "tcp_background": True,
        })
        # More stations — higher contention for BG slots
        add("tcp_many_stations", {
            "stations": 16,
            "background_mbps": 15.0,
            "deadline_s": 0.020,
            "tcp_background": True,
        })

    # ------------------------------------------------------------------
    # Extensions 4 + 5 — Multi-AP / OBSS interference sweep
    # medium_stolen_fraction models the fraction of channel slots stolen
    # by an overlapping BSS or uplink traffic, degrading effective
    # medium availability for the AP's downlink scheduler.
    # ------------------------------------------------------------------
    elif args.suite == "obss":
        base_obss = {
            "stations": 8,
            "background_mbps": 12.0,
            "deadline_s": 0.020,
        }
        add("obss_clean", base_obss)   # no interference — clean reference

        # Sweep OBSS stolen fraction (5 % → 40 %)
        for stolen in [0.05, 0.10, 0.20, 0.30, 0.40]:
            add(f"obss_stolen_{stolen:g}", {
                **base_obss,
                "medium_stolen_fraction": stolen,
            })

        # Uplink contention (station sends uplink while AP tries downlink)
        # Uplink occupies ~50 % of BG medium → medium_stolen_fraction ≈ 0.25
        for uplink_fraction in [0.30, 0.50, 0.70]:
            effective_stolen = uplink_fraction * 0.50
            add(f"obss_uplink_{uplink_fraction:g}", {
                **base_obss,
                "medium_stolen_fraction": effective_stolen,
            })

        # Tight RT deadline under OBSS — most sensitive scenario
        add("obss_tight_deadline", {
            **base_obss,
            "deadline_s": 0.010,
            "medium_stolen_fraction": 0.20,
        })

        # Bursty OBSS (interferer is also bursty)
        add("obss_bursty_interferer", {
            **base_obss,
            "medium_stolen_fraction": 0.20,
            "background_bursty": True,
        })

        # Two-AP scenario: heavy OBSS load
        add("obss_two_ap_heavy", {
            **base_obss,
            "medium_stolen_fraction": 0.35,
            "bad_enter": 0.15,
        })

    return cases


def clean_json(value):
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean_json(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def source_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_output(root, output, args, cases):
    files = [
        "schedulers.py",
        "test_schedulers.py",
        "simulator.py",
        "test_simulator.py",
        "run_all.py",
    ]

    experiment = clean_json({
        "suite": args.suite,
        "seeds": args.seeds,
        "first_seed": args.first_seed,
        "packet_logs": args.packet_logs,
        "policies": POLICIES,
        "cases": [
            {
                "case": name,
                "model": asdict(model),
                "scheduler": asdict(scheduler),
            }
            for name, model, scheduler in cases
        ],
        "source_hashes": {
            name: source_hash(root / name) for name in files
        },
    })

    output.mkdir(exist_ok=True)
    manifest_path = output / "manifest.json"

    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))

        if saved["experiment"] != experiment:
            raise ValueError(
                "Configuration or source files changed. "
                "Choose a new --out folder."
            )

        if not (args.resume or args.analyse_only):
            raise ValueError(
                "Results already exist. Use --resume or --analyse-only."
            )
    else:
        if args.analyse_only:
            raise ValueError("No existing experiment to analyse.")
        if any(output.iterdir()):
            raise ValueError("Output folder must initially be empty.")

        manifest = {
            "experiment": experiment,
            "environment": {
                "python": sys.version,
                "platform": platform.platform(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "scipy": scipy.__version__,
                "matplotlib": matplotlib.__version__,
            },
        }

        manifest_path.write_text(
            json.dumps(manifest, indent=2, allow_nan=False),
            encoding="utf-8",
        )

    for folder in ("raw", "tables", "plots"):
        (output / folder).mkdir(exist_ok=True)

    configuration_rows = []
    for name, model, scheduler in cases:
        configuration_rows.append({
            "case": name,
            **{
                f"model_{key}": value
                for key, value in asdict(model).items()
            },
            **{
                f"scheduler_{key}": value
                for key, value in asdict(scheduler).items()
            },
        })

    pd.DataFrame(configuration_rows).to_csv(
        output / "tables" / "configurations.csv", index=False
    )


def validate_record(record, case, seed, policy):
    if (
        record.get("case") != case
        or record.get("seed") != seed
        or record.get("policy") != policy
    ):
        raise ValueError("Cached result identity mismatch.")

    if not set(DESCRIPTIVE).issubset(record):
        raise ValueError("Cached result is missing metrics.")

    for kind in ("rt", "bg"):
        total = sum(
            record[f"{kind}_{status}"]
            for status in (
                "delivered",
                "expired",
                "overflow",
                "retry_failed",
                "outstanding",
            )
        )
        if total != record[f"{kind}_generated"]:
            raise ValueError("Packet conservation check failed.")


def run_experiments(output, args, cases):
    total = len(cases) * args.seeds * len(POLICIES)
    completed = 0
    records = []

    print(
        f"\n{len(cases)} configurations × {args.seeds} seeds × "
        f"{len(POLICIES)} policies = {total} simulations",
        flush=True,
    )

    for case, model, scheduler in cases:
        for seed in range(
            args.first_seed, args.first_seed + args.seeds
        ):
            workload = None

            for policy in POLICIES:
                completed += 1
                path = output / "raw" / (
                    f"{case}__seed{seed}__{policy}.json"
                )

                if path.exists():
                    record = json.loads(
                        path.read_text(encoding="utf-8")
                    )
                    validate_record(record, case, seed, policy)
                    action = "reused"
                else:
                    if args.analyse_only:
                        raise FileNotFoundError(
                            f"Missing {path.name}; use --resume."
                        )

                    if workload is None:
                        workload = make_workload(model, seed)

                    start = time.perf_counter()
                    result = simulate(
                        workload,
                        policy,
                        scheduler,
                        packet_logs=args.packet_logs,
                    )
                    elapsed = time.perf_counter() - start

                    record = clean_json({
                        "case": case,
                        "seed": seed,
                        "policy": policy,
                        **result,
                        "simulation_wall_seconds": elapsed,
                    })
                    validate_record(record, case, seed, policy)

                    temporary = path.with_suffix(".tmp")
                    temporary.write_text(
                        json.dumps(record, indent=2, allow_nan=False),
                        encoding="utf-8",
                    )
                    temporary.replace(path)
                    action = "finished"

                # Keep large packet logs and station arrays in raw JSON,
                # rather than duplicating them in the combined CSV.
                records.append({
                    key: value
                    for key, value in record.items()
                    if not isinstance(value, (list, dict))
                })

                print(
                    f"[{completed}/{total}] {action}: "
                    f"{case}, seed={seed}, {policy}",
                    flush=True,
                )

    frame = pd.DataFrame(records)

    if frame.duplicated(["case", "seed", "policy"]).any():
        raise ValueError("Duplicate simulation records.")

    for metric in DESCRIPTIVE:
        frame[metric] = pd.to_numeric(frame[metric], errors="raise")

    frame.to_csv(output / "tables" / "all_runs.csv", index=False)
    return frame


def bootstrap_ci(values, repetitions, rng):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]

    if len(values) < 2:
        return np.nan, np.nan
    if np.all(values == values[0]):
        return float(values[0]), float(values[0])

    estimates = np.empty(repetitions)

    for start in range(0, repetitions, 1000):
        size = min(1000, repetitions - start)
        indices = rng.integers(
            0, len(values), size=(size, len(values))
        )
        estimates[start:start + size] = values[indices].mean(axis=1)

    low, high = np.quantile(estimates, [0.025, 0.975])
    return float(low), float(high)


def holm_adjust(values):
    values = np.asarray(values, dtype=float)
    adjusted = np.full(len(values), np.nan)
    valid = np.flatnonzero(np.isfinite(values))

    if not len(valid):
        return adjusted

    order = valid[np.argsort(values[valid])]
    corrected = values[order] * (len(order) - np.arange(len(order)))
    adjusted[order] = np.minimum(
        np.maximum.accumulate(corrected), 1.0
    )
    return adjusted


def rank_biserial(differences):
    nonzero = differences[differences != 0]

    if not len(nonzero):
        return 0.0

    ranks = rankdata(np.abs(nonzero))
    return float(
        (
            ranks[nonzero > 0].sum()
            - ranks[nonzero < 0].sum()
        ) / ranks.sum()
    )


def summarise(frame, args, rng):
    rows = []

    for (case, policy), group in frame.groupby(["case", "policy"]):
        for metric in DESCRIPTIVE:
            values = group[metric].dropna().to_numpy(dtype=float)
            low, high = bootstrap_ci(values, args.bootstrap, rng)

            rows.append({
                "case": case,
                "policy": policy,
                "metric": metric,
                "n_valid": len(values),
                "n_missing": len(group) - len(values),
                "mean": np.mean(values) if len(values) else np.nan,
                "std": (
                    np.std(values, ddof=1)
                    if len(values) > 1 else np.nan
                ),
                "median": np.median(values) if len(values) else np.nan,
                "minimum": np.min(values) if len(values) else np.nan,
                "maximum": np.max(values) if len(values) else np.nan,
                "ci_low": low,
                "ci_high": high,
            })

    return pd.DataFrame(rows)


def compare_paired(frame, args, rng):
    rows = []

    for case, group in frame.groupby("case"):
        proposed = group[
            group["policy"] == "proposed"
        ].set_index("seed")

        for comparator in POLICIES:
            if comparator == "proposed":
                continue

            baseline = group[
                group["policy"] == comparator
            ].set_index("seed")

            for metric, (_, direction) in METRICS.items():
                pairs = pd.concat(
                    [
                        proposed[metric].rename("proposed"),
                        baseline[metric].rename("baseline"),
                    ],
                    axis=1,
                    join="inner",
                ).dropna()

                differences = (
                    pairs["proposed"] - pairs["baseline"]
                ).to_numpy(dtype=float)

                n = len(differences)
                low, high = bootstrap_ci(
                    differences, args.bootstrap, rng
                )

                mean = (
                    float(np.mean(differences)) if n else np.nan
                )
                sd = (
                    float(np.std(differences, ddof=1))
                    if n > 1 else np.nan
                )

                p_value = np.nan
                if n >= 5:
                    if np.all(differences == 0):
                        p_value = 1.0
                    else:
                        p_value = float(wilcoxon(
                            differences,
                            alternative="two-sided",
                            zero_method="wilcox",
                            method="auto",
                        ).pvalue)

                rows.append({
                    "case": case,
                    "comparator": comparator,
                    "metric": metric,
                    "n_pairs": n,
                    "n_missing_pairs": args.seeds - n,
                    "proposed_mean": (
                        pairs["proposed"].mean() if n else np.nan
                    ),
                    "baseline_mean": (
                        pairs["baseline"].mean() if n else np.nan
                    ),
                    "mean_difference": mean,
                    "difference_ci_low": low,
                    "difference_ci_high": high,
                    "mean_improvement": direction * mean,
                    "improvement_ci_low": (
                        low if direction == 1 else -high
                    ),
                    "improvement_ci_high": (
                        high if direction == 1 else -low
                    ),
                    "paired_cohens_dz": (
                        mean / sd
                        if np.isfinite(sd) and sd > 0 else np.nan
                    ),
                    "oriented_rank_biserial": (
                        direction * rank_biserial(differences)
                        if n else np.nan
                    ),
                    "run_win_fraction": (
                        np.mean(direction * differences > 0)
                        if n else np.nan
                    ),
                    "run_tie_fraction": (
                        np.mean(differences == 0) if n else np.nan
                    ),
                    "wilcoxon_p": p_value,
                })

    result = pd.DataFrame(rows)

    # Global correction within this suite:
    # all configurations, metrics, and comparators.
    result["holm_p"] = holm_adjust(
        result["wilcoxon_p"].to_numpy()
    )
    result["reject_after_holm"] = result["holm_p"] < 0.05

    return result


def save_table(frame, output, name):
    frame.to_csv(output / "tables" / f"{name}.csv", index=False)

    def cell(value):
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            return f"{value:.6g}"
        return str(value).replace("|", "/").replace("\n", " ")

    lines = [
        "| " + " | ".join(frame.columns) + " |",
        "| " + " | ".join("---" for _ in frame.columns) + " |",
    ]

    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(cell(v) for v in row) + " |")

    (output / "tables" / f"{name}.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def save_figure(fig, output, name):
    for extension in ("png", "pdf"):
        fig.savefig(
            output / "plots" / f"{name}.{extension}",
            dpi=220,
            bbox_inches="tight",
        )
    plt.close(fig)


def make_plots(frame, summary, comparisons, output, analysis_seed):
    rng = np.random.default_rng(analysis_seed + 1)

    plt.rcParams.update({
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.2,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    comparators = [p for p in POLICIES if p != "proposed"]

    for case, group in frame.groupby("case"):
        case_summary = summary[summary["case"] == case]

        fig, axes = plt.subplots(4, 2, figsize=(15, 18))

        for axis, (metric, (label, _)) in zip(
            axes.flat, METRICS.items()
        ):
            for position, policy in enumerate(POLICIES):
                values = group.loc[
                    group["policy"] == policy, metric
                ].dropna().to_numpy(dtype=float)

                axis.scatter(
                    position + rng.uniform(-0.13, 0.13, len(values)),
                    values,
                    color=COLORS[policy],
                    alpha=0.35,
                    s=14,
                )

                row = case_summary[
                    (case_summary["policy"] == policy)
                    & (case_summary["metric"] == metric)
                ].iloc[0]

                if np.isfinite(row["mean"]):
                    axis.plot(
                        position, row["mean"], "kD", markersize=5
                    )

                if np.isfinite(row["ci_low"]):
                    axis.vlines(
                        position,
                        row["ci_low"],
                        row["ci_high"],
                        color="black",
                        linewidth=2,
                    )

            axis.set_xticks(range(len(POLICIES)))
            axis.set_xticklabels(POLICIES, rotation=35, ha="right")
            axis.set_ylabel(label)

        # Eighth panel: reliability/background-throughput trade-off.
        axis = axes.flat[-1]

        for policy in POLICIES:
            selected = group[group["policy"] == policy]

            axis.scatter(
                selected["rt_miss_fraction"],
                selected["bg_goodput_mbps"],
                color=COLORS[policy],
                alpha=0.2,
                s=15,
            )
            axis.scatter(
                selected["rt_miss_fraction"].mean(),
                selected["bg_goodput_mbps"].mean(),
                color=COLORS[policy],
                marker="D",
                s=50,
                label=policy,
            )

        axis.set_xlabel("Deadline misses: lower is better")
        axis.set_ylabel("Background Mbps: higher is better")
        axis.legend(fontsize=7)

        fig.suptitle(
            f"{case}\nPoints: runs; diamonds: means; "
            "vertical lines: 95% bootstrap confidence intervals"
        )
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        save_figure(fig, output, f"{case}_metrics")

        fig, axes = plt.subplots(4, 2, figsize=(15, 18))

        for axis, (metric, (label, _)) in zip(
            axes.flat, METRICS.items()
        ):
            selected = comparisons[
                (comparisons["case"] == case)
                & (comparisons["metric"] == metric)
            ].set_index("comparator")

            for position, comparator in enumerate(comparators):
                row = selected.loc[comparator]

                if np.isfinite(row["mean_improvement"]):
                    axis.plot(
                        row["mean_improvement"],
                        position,
                        marker=(
                            "*" if row["reject_after_holm"] else "o"
                        ),
                        markersize=9,
                        color=COLORS[comparator],
                    )

                if np.isfinite(row["improvement_ci_low"]):
                    axis.hlines(
                        position,
                        row["improvement_ci_low"],
                        row["improvement_ci_high"],
                        color=COLORS[comparator],
                        linewidth=2,
                    )

            axis.axvline(0, color="black", linestyle="--")
            axis.set_yticks(range(len(comparators)))
            axis.set_yticklabels(comparators)
            axis.set_xlabel(f"Improvement in original units →\n{label}")

        axes.flat[-1].axis("off")

        fig.suptitle(
            f"{case}\nPositive improvement favors proposed.\n"
            "Intervals: unadjusted 95% paired bootstrap CIs; "
            "stars: Holm-significant two-sided tests."
        )
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        save_figure(fig, output, f"{case}_paired")


def write_report(frame, comparisons, args, cases, output):
    settings = {
        "bootstrap_repetitions": args.bootstrap,
        "analysis_seed": args.analysis_seed,
        "confidence_level": 0.95,
        "significance_threshold": 0.05,
        "test": "two-sided paired Wilcoxon signed-rank",
        "multiplicity": "Holm across all valid tests in this suite",
    }

    (output / "analysis_settings.json").write_text(
        json.dumps(settings, indent=2),
        encoding="utf-8",
    )

    report = f"""# Scheduling experiment report

## Experiment

- Suite: {args.suite}
- Configurations: {len(cases)}
- Policies: {len(POLICIES)}
- Seeds per configuration/policy: {args.seeds}
- Seed range: {args.first_seed}–{args.first_seed + args.seeds - 1}
- Simulation records: {len(frame)}
- Offered-traffic duration: {args.duration} seconds
- Drain duration: {args.drain} seconds
- Bootstrap repetitions: {args.bootstrap}
- Valid hypothesis tests: {comparisons["wilcoxon_p"].notna().sum()}

## Methods

One simulation run is the experimental unit, not one packet.

Every policy receives the same generated workload for each case and seed.
Exogenous channel states and packet-attempt draws are independent of policy
execution order.

Summary tables contain mean, sample standard deviation, median, range,
valid/missing counts, and percentile-bootstrap 95% confidence intervals.

Comparisons pair results by case and seed. Mean differences are proposed
minus comparator. Oriented improvements reverse signs for lower-is-better
metrics, so positive values favor proposed.

Comparison intervals bootstrap paired differences. They are pointwise,
unadjusted intervals, not simultaneous confidence intervals.

Two-sided Wilcoxon signed-rank tests use Holm correction across all valid
tests in this suite. A location interpretation of Wilcoxon requires
appropriate assumptions, including symmetry of paired differences.
The tests do not directly test the mean differences shown in the plots.

Paired Cohen's dz, oriented rank-biserial effects, and run-win/tie fractions
are reported. Undefined statistics remain missing.

CPU-time measurements are descriptive only and are excluded from the
hypothesis-test family.

## Missing data and interpretation

Received-packet delay excludes undelivered packets. Read latency alongside
deadline misses, delivery fractions, and outstanding-packet counts.

Paired comparisons use complete pairs and report missing-pair counts.
Different missingness between algorithms can bias latency comparisons.

Background delivery fraction is a packet statistic, not application-flow
completion. Background goodput excludes the drain interval, while delivery
fractions can include packets received during drain.

Service-time fairness includes modeled backoff and protocol overhead.
Airtime fairness uses modeled on-air intervals and is a different metric.

Scheduler microseconds measure Python choose/complete calls. They are not
deployment overhead estimates or reliable cross-machine benchmarks.
Policy execution order is fixed, so caching/load effects can affect timings.

Mean attempt counts exclude a transmission interrupted at simulation end.

## Limits and experimental design

This is not a standards-compliant Wi-Fi MAC/PHY simulator.

The model excludes competing APs, uplink contention, full aggregation,
OFDMA, and TCP congestion control. Channel/rate sweeps are not physical
distance or interference validation.

Most sweeps change one factor at a time; they do not exhaust interactions.
Changing station count also changes total real-time offered traffic.
There is no explicit warm-up exclusion.

Background reservation is a heuristic, not a guaranteed service bound.
Baselines are established approaches, not verified current state of the art.
Recent research baselines and fair baseline-specific tuning remain necessary.

Forty seeds do not guarantee adequate power. Statistical significance does
not establish practical importance, novelty, or real-world superiority.

Constant outcomes may produce zero-width bootstrap intervals. This does
not establish certainty outside the modeled experiment.

Tune parameters using tuning data, freeze the choice, then evaluate.
Do not select the final algorithm using evaluation results and still call
those results held out. Tuning does not automatically optimize all baselines.

Holm correction is per suite. Claims combining suites require appropriate
combined analysis rather than treating each suite as independent evidence.

## Outputs

- manifest.json: configuration, environment, source fingerprints
- analysis_settings.json: statistical settings
- raw/: individual simulation JSON records
- tables/configurations.csv: model and scheduler settings
- tables/all_runs.csv: scalar run-level results
- tables/summary.csv and .md: descriptive statistics
- tables/comparisons.csv and .md: paired statistical comparisons
- plots/: PNG and PDF figures

Raw records include per-station service and airtime values.
Packet-level records are included only when --packet-logs is enabled.

## Publication status

These experiments evaluate this implementation and model only.
A current literature review, simulator validation, and stronger comparative
evidence are required before making publication-readiness claims.
"""

    (output / "REPORT.md").write_text(report, encoding="utf-8")


def main():
    args = parse_args()
    root = Path(__file__).resolve().parent
    output = root / args.out
    cases = build_cases(args)

    prepare_output(root, output, args, cases)

    if not args.analyse_only:
        print("Running correctness tests...", flush=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "-v",
                "test_schedulers",
                "test_simulator",
            ],
            cwd=root,
            check=True,
        )

    frame = run_experiments(output, args, cases)

    print("\nComputing statistics...", flush=True)
    rng = np.random.default_rng(args.analysis_seed)

    summary = summarise(frame, args, rng)
    comparisons = compare_paired(frame, args, rng)

    save_table(summary, output, "summary")
    save_table(comparisons, output, "comparisons")

    print("Generating plots...", flush=True)
    make_plots(
        frame,
        summary,
        comparisons,
        output,
        args.analysis_seed,
    )

    write_report(frame, comparisons, args, cases, output)

    print(f"\nFinished. Results saved in:\n{output}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\nInterrupted. Completed runs are saved. "
            "Repeat the same command with --resume.",
            file=sys.stderr,
        )
        sys.exit(130)
    except (
        ValueError,
        OSError,
        subprocess.CalledProcessError,
        AssertionError,
    ) as error:
        print(
            f"\nFailed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        sys.exit(1)
