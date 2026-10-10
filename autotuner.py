#!/usr/bin/env python3
"""
Extension 2 — Adaptive Parameter Auto-Tuning for U-AFS.

Uses Simultaneous Perturbation Stochastic Approximation (SPSA) to
dynamically optimise the four frozen U-AFS parameters:

    H_u  (urgency_horizon_s)  : urgency detection window
    w_f  (fairness_weight)    : fairness term coefficient
    α_bg (background_share)   : background debt increment rate
    Q    (quantum_s)          : DRR quantum

The gradient estimate requires only TWO objective evaluations per step,
regardless of parameter dimension — cheap enough to run overnight.

Objective
---------
    J(θ) = λ_rt · (1 − rt_miss) + λ_fair · jain + λ_bg · bg_delivery

where λ_rt=0.50, λ_fair=0.30, λ_bg=0.20.

SPSA update (maximising J):
    θ_{k+1} = θ_k + a_k · ĝ_k
    ĝ_k = [J(θ+c_k Δ) − J(θ−c_k Δ)] / (2 c_k Δ)   Δ ~ Bernoulli(±1)^4

Usage
-----
    # Tune with 200 iterations (default)
    python autotuner.py

    # Faster test run
    python autotuner.py --n-iter 50 --train-seeds 5 --held-seeds 5

    # Tune a different policy
    python autotuner.py --policy no_fairness

    # Custom output folder
    python autotuner.py --out my_tuning

Outputs  (<out>/)
-------
    best_params.json   — optimised SchedulerConfig (embed in paper Table)
    convergence.json   — per-iteration J(θ) history
    held_out.json      — frozen vs tuned metric comparison on held-out seeds
    convergence.png/pdf
    comparison.png/pdf
"""

import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from dataclasses import asdict, replace

from schedulers import SchedulerConfig
from simulator import ModelConfig, make_workload, simulate


# ============================================================
# Hyper-parameters
# ============================================================

PARAM_KEYS = [
    "urgency_horizon_s",   # H_u
    "fairness_weight",     # w_f
    "background_share",    # α_bg
    "quantum_s",           # Q
]

PARAM_BOUNDS = {
    "urgency_horizon_s": (0.002, 0.060),
    "fairness_weight":   (0.02,  2.00),
    "background_share":  (0.05,  0.50),
    "quantum_s":         (0.0003, 0.012),
}

OBJ_WEIGHTS = {"rt": 0.50, "fair": 0.30, "bg": 0.20}

# Default model — mirrors run_all.py "reference" case
DEFAULT_MODEL = ModelConfig(
    duration_s=10.0,
    drain_s=1.0,
    stations=12,
    background_mbps=18.0,
    deadline_s=0.025,
)

# Frozen defaults from SchedulerConfig
FROZEN_THETA = {
    "urgency_horizon_s": 0.010,
    "fairness_weight":   0.25,
    "background_share":  0.20,
    "quantum_s":         0.001,
}


# ============================================================
# Parameter vector helpers
# ============================================================

def clip(theta: np.ndarray) -> np.ndarray:
    """Project θ into the feasible box."""
    return np.array([
        np.clip(theta[i],
                PARAM_BOUNDS[PARAM_KEYS[i]][0],
                PARAM_BOUNDS[PARAM_KEYS[i]][1])
        for i in range(len(PARAM_KEYS))
    ])


def theta_to_config(theta: np.ndarray,
                    base: SchedulerConfig) -> SchedulerConfig:
    return replace(
        base,
        urgency_horizon_s=float(theta[0]),
        fairness_weight=float(theta[1]),
        background_share=float(theta[2]),
        quantum_s=float(theta[3]),
    )


def config_to_theta(cfg: SchedulerConfig) -> np.ndarray:
    return np.array([getattr(cfg, k) for k in PARAM_KEYS])


def frozen_config(base: SchedulerConfig) -> SchedulerConfig:
    return replace(base, **FROZEN_THETA)


# ============================================================
# Objective function J(θ)
# ============================================================

def evaluate(theta: np.ndarray,
             model: ModelConfig,
             policy: str,
             base_sched: SchedulerConfig,
             seeds: list) -> dict:
    """
    Run simulate() over `seeds`, return averaged metric dict.

    Returns a dict with keys:
        J              — composite objective (higher is better)
        rt_score       — 1 − rt_miss_fraction
        fair_score     — service_jain
        bg_score       — bg_delivery_fraction
        rt_miss        — raw rt_miss_fraction
        jain           — raw service_jain
        bg_delivery    — raw bg_delivery_fraction
    NaN is returned for infeasible θ.
    """
    try:
        sched = theta_to_config(clip(theta), base_sched)
    except (ValueError, TypeError):
        return _nan_result()

    rt_list, jain_list, bg_list = [], [], []

    for seed in seeds:
        try:
            wl = make_workload(model, seed)
            r  = simulate(wl, policy, sched)
        except Exception:
            continue

        _append_safe(rt_list,   r.get("rt_miss_fraction"))
        _append_safe(jain_list, r.get("service_jain"))
        _append_safe(bg_list,   r.get("bg_delivery_fraction"))

    if not rt_list:
        return _nan_result()

    rt_mean   = float(np.mean(rt_list))
    jain_mean = float(np.mean(jain_list))
    bg_mean   = float(np.mean(bg_list))

    rt_score   = 1.0 - rt_mean
    fair_score = jain_mean
    bg_score   = min(bg_mean, 1.0)

    J = (OBJ_WEIGHTS["rt"]   * rt_score
         + OBJ_WEIGHTS["fair"] * fair_score
         + OBJ_WEIGHTS["bg"]   * bg_score)

    return dict(J=J, rt_score=rt_score, fair_score=fair_score,
                bg_score=bg_score, rt_miss=rt_mean,
                jain=jain_mean, bg_delivery=bg_mean)


def _append_safe(lst, val):
    if val is not None and math.isfinite(val):
        lst.append(float(val))


def _nan_result():
    return dict(J=math.nan, rt_score=math.nan, fair_score=math.nan,
                bg_score=math.nan, rt_miss=math.nan,
                jain=math.nan, bg_delivery=math.nan)


# ============================================================
# SPSA optimiser
# ============================================================

def spsa_tune(model: ModelConfig,
              policy: str,
              base_sched: SchedulerConfig,
              train_seeds: list,
              n_iter: int = 200,
              a: float = 0.008,
              c: float = 0.004,
              alpha: float = 0.602,
              gamma: float = 0.101,
              rng_seed: int = 7) -> tuple:
    """
    Maximise J(θ) over `train_seeds` using SPSA.

    Returns (best_theta, history_list).
    history_list contains one dict per iteration with keys:
        k, J, J_plus, J_minus, theta, rt_score, fair_score, bg_score
    """
    rng = np.random.default_rng(rng_seed)
    theta = config_to_theta(frozen_config(base_sched))
    A = 0.1 * n_iter     # stability constant

    best_theta = theta.copy()
    best_J = -math.inf
    history = []

    print(f"\nSPSA: {n_iter} iterations | policy={policy} | "
          f"train seeds: {train_seeds[0]}-{train_seeds[-1]}")
    _print_theta("Initial theta", theta)

    for k in range(1, n_iter + 1):
        ak = a / (k + A) ** alpha
        ck = c / k ** gamma

        # Bernoulli(±1) perturbation
        delta = rng.choice([-1.0, 1.0], size=len(theta))

        J_plus  = evaluate(clip(theta + ck * delta),
                           model, policy, base_sched, train_seeds)["J"]
        J_minus = evaluate(clip(theta - ck * delta),
                           model, policy, base_sched, train_seeds)["J"]

        if not (math.isfinite(J_plus) and math.isfinite(J_minus)):
            history.append(dict(k=k, J=math.nan, theta=theta.tolist()))
            continue

        # Gradient estimate (sign: maximising J → add a_k * g_hat)
        g_hat = (J_plus - J_minus) / (2.0 * ck * delta)
        theta  = clip(theta + ak * g_hat)

        probe  = evaluate(theta, model, policy, base_sched, train_seeds)
        J_now  = probe["J"]

        if math.isfinite(J_now) and J_now > best_J:
            best_J     = J_now
            best_theta = theta.copy()

        history.append(dict(
            k=k, J=J_now,
            J_plus=J_plus, J_minus=J_minus,
            theta=theta.tolist(),
            rt_score=probe.get("rt_score"),
            fair_score=probe.get("fair_score"),
            bg_score=probe.get("bg_score"),
        ))

        if k % max(1, n_iter // 10) == 0 or k == 1:
            print(f"  iter {k:4d}/{n_iter}: "
                  f"J={J_now:.4f}  "
                  f"rt={probe.get('rt_score', 0.0):.3f}  "
                  f"fair={probe.get('fair_score', 0.0):.3f}  "
                  f"bg={probe.get('bg_score', 0.0):.3f}")

    print(f"\nBest J={best_J:.4f}")
    _print_theta("Best theta", best_theta)
    return best_theta, history


def _print_theta(label, theta):
    parts = ", ".join(f"{k}={v:.5g}"
                      for k, v in zip(PARAM_KEYS, theta))
    print(f"  {label}: [{parts}]")


# ============================================================
# Held-out evaluation
# ============================================================

def held_out_comparison(model, policy, base_sched,
                        tuned_theta, held_seeds) -> dict:
    """Compare frozen vs tuned on the held-out seed set."""
    frozen_theta = config_to_theta(frozen_config(base_sched))

    r_frozen = evaluate(frozen_theta, model, policy, base_sched, held_seeds)
    r_tuned  = evaluate(tuned_theta,  model, policy, base_sched, held_seeds)

    deltas = {}
    for key in ("J", "rt_miss", "jain", "bg_delivery"):
        vf = r_frozen.get(key, math.nan)
        vt = r_tuned.get(key, math.nan)
        deltas[f"delta_{key}"] = (
            vt - vf if math.isfinite(vt) and math.isfinite(vf)
            else math.nan
        )

    return dict(frozen=r_frozen, tuned=r_tuned, **deltas)


# ============================================================
# Plots
# ============================================================

def plot_convergence(history: list, out_dir: Path, n_iter: int):
    plt.rcParams.update({"font.size": 9, "axes.grid": True,
                         "grid.alpha": 0.3,
                         "axes.spines.top": False,
                         "axes.spines.right": False})

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    ks = [h["k"] for h in history]
    Js = [h.get("J") for h in history]

    # ── Left: objective trace ──────────────────────────────────────────
    ax = axes[0]
    ax.plot(ks, Js, color="#0072B2", linewidth=1.2, label="J(θ) per iter")
    finite = [j for j in Js if j is not None and math.isfinite(j)]
    if finite:
        ax.axhline(max(finite), color="#D55E00", linestyle="--",
                   linewidth=1.2, label=f"Best J = {max(finite):.4f}")
    ax.set_xlabel("SPSA Iteration  k")
    ax.set_ylabel("Objective  J(θ)")
    ax.set_title("SPSA Convergence  (training seeds)")
    ax.legend(fontsize=8)

    # ── Right: component traces ────────────────────────────────────────
    ax = axes[1]
    comps = [
        ("rt_score",    "#E69F00", "RT reliability  1−rt_miss"),
        ("fair_score",  "#009E73", "Jain fairness"),
        ("bg_score",    "#CC79A7", "BG delivery fraction"),
    ]
    for key, color, label in comps:
        vals = [h.get(key) for h in history]
        ax.plot(ks, vals, color=color, linewidth=1.0,
                alpha=0.85, label=label)
    ax.set_xlabel("SPSA Iteration  k")
    ax.set_ylabel("Component score")
    ax.set_title("Objective components vs iteration")
    ax.legend(fontsize=7)

    fig.suptitle("U-AFS SPSA Parameter Auto-Tuning  (Extension 2)",
                 fontsize=11, y=1.01)
    fig.tight_layout()
    _save_fig(fig, out_dir, "convergence")


def plot_comparison(held: dict, out_dir: Path):
    plt.rcParams.update({"font.size": 9,
                         "axes.spines.top": False,
                         "axes.spines.right": False})

    metrics = [
        ("rt_miss",    "RT miss fraction",       True,  "#E69F00"),
        ("jain",       "Service Jain fairness",   False, "#009E73"),
        ("bg_delivery","BG delivery fraction",    False, "#CC79A7"),
        ("J",          "Composite J(θ)",          False, "#0072B2"),
    ]
    fig, axes = plt.subplots(1, len(metrics), figsize=(14, 3.8))

    for ax, (key, label, lower_better, color) in zip(axes, metrics):
        vf = held["frozen"].get(key, math.nan)
        vt = held["tuned"].get(key, math.nan)
        bars = ax.bar(["Frozen\n(paper)", "SPSA\ntuned"],
                      [vf, vt],
                      color=["#BBBBBB", color],
                      edgecolor="black", linewidth=0.7)
        ax.set_title(label, fontsize=9)
        ax.set_ylabel("lower better" if lower_better else "higher better",
                       fontsize=8)
        ax.grid(axis="y", alpha=0.3)
        # Annotate delta
        dk = f"delta_{key}"
        if dk in held and math.isfinite(held[dk]):
            sign = "+" if held[dk] >= 0 else ""
            ax.set_xlabel(f"Delta = {sign}{held[dk]:.4f}", fontsize=8)

    fig.suptitle(
        "Frozen vs. SPSA-Tuned Parameters — Held-out seeds  (Extension 2)",
        fontsize=10, y=1.01)
    fig.tight_layout()
    _save_fig(fig, out_dir, "comparison")


def _save_fig(fig, out_dir, name):
    for ext in ("png", "pdf"):
        fig.savefig(out_dir / f"{name}.{ext}", dpi=200,
                    bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {name}.png")


# ============================================================
# JSON serialisation
# ============================================================

def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if not math.isfinite(obj) else float(obj)
    return obj


# ============================================================
# CLI
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="SPSA adaptive parameter tuner for U-AFS (Extension 2).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--policy", default="proposed",
                   help="Scheduler policy to tune")
    p.add_argument("--n-iter", type=int, default=200,
                   help="SPSA iterations")
    p.add_argument("--train-seeds", type=int, default=20,
                   help="Number of training seeds (starting at 42)")
    p.add_argument("--held-seeds", type=int, default=20,
                   help="Number of held-out seeds (starting at 2000)")
    p.add_argument("--out", default="tuning_results",
                   help="Output directory name (relative to this script)")
    p.add_argument("--a",     type=float, default=0.008,
                   help="SPSA step-size coefficient a")
    p.add_argument("--c",     type=float, default=0.004,
                   help="SPSA perturbation coefficient c")
    p.add_argument("--rng-seed", type=int, default=7,
                   help="RNG seed for SPSA perturbations")
    return p.parse_args()


def main():
    args = parse_args()

    root    = Path(__file__).resolve().parent
    out_dir = root / args.out
    out_dir.mkdir(exist_ok=True)

    train_seeds   = list(range(42, 42 + args.train_seeds))
    held_seeds    = list(range(2000, 2000 + args.held_seeds))

    base_sched = SchedulerConfig(stations=DEFAULT_MODEL.stations)

    print("=" * 62)
    print("  U-AFS Extension 2 - SPSA Parameter Auto-Tuner")
    print("=" * 62)
    print(f"  Policy      : {args.policy}")
    print(f"  SPSA iters  : {args.n_iter}")
    print(f"  Train seeds : {train_seeds[0]}–{train_seeds[-1]}")
    print(f"  Held-out    : {held_seeds[0]}–{held_seeds[-1]}")
    print(f"  Output      : {out_dir}")
    print()

    # Baseline: frozen parameters on training seeds
    print(" Baseline (frozen theta, training seeds) ")
    frozen_theta = config_to_theta(frozen_config(base_sched))
    r_base = evaluate(frozen_theta, DEFAULT_MODEL, args.policy,
                      base_sched, train_seeds)
    print(f"  J={r_base['J']:.4f}  "
          f"rt_miss={r_base['rt_miss']:.4f}  "
          f"jain={r_base['jain']:.4f}  "
          f"bg={r_base['bg_delivery']:.4f}\n")

    # SPSA optimisation
    best_theta, history = spsa_tune(
        DEFAULT_MODEL, args.policy, base_sched,
        train_seeds=train_seeds,
        n_iter=args.n_iter,
        a=args.a, c=args.c,
        rng_seed=args.rng_seed,
    )

    tuned_sched = theta_to_config(best_theta, base_sched)

    # Parameter change summary
    print(" Parameter changes ")
    header = f"  {'Parameter':25s}  {'Frozen':>10s}  {'Tuned':>10s}  {'Δ%':>8s}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for key, val in zip(PARAM_KEYS, best_theta):
        fval = FROZEN_THETA[key]
        pct  = 100.0 * (val - fval) / fval if fval else 0.0
        print(f"  {key:25s}  {fval:10.5f}  {val:10.5f}  {pct:+8.1f}pct")

    # Held-out evaluation
    print(" Held-out evaluation ")
    held = held_out_comparison(
        DEFAULT_MODEL, args.policy, base_sched, best_theta, held_seeds
    )
    print(f"  Frozen J  = {held['frozen']['J']:.4f}")
    print(f"  Tuned  J  = {held['tuned']['J']:.4f}")
    print(f"  Delta J        = {held['delta_J']:+.4f}")
    print(f"  Delta rt_miss = {held['delta_rt_miss']:+.4f}  "
          f"(-ve = fewer misses)")
    print(f"  Delta jain    = {held['delta_jain']:+.4f}  "
          f"(+ve = better fairness)")
    print(f"  Delta bg_del  = {held['delta_bg_delivery']:+.4f}  "
          f"(+ve = better BG delivery)")

    # Save outputs
    print(" Saving outputs ")
    (out_dir / "convergence.json").write_text(
        json.dumps(_clean(history), indent=2), encoding="utf-8")
    (out_dir / "best_params.json").write_text(
        json.dumps(_clean(asdict(tuned_sched)), indent=2), encoding="utf-8")
    (out_dir / "held_out.json").write_text(
        json.dumps(_clean(held), indent=2), encoding="utf-8")

    plot_convergence(history, out_dir, args.n_iter)
    plot_comparison(held, out_dir)

    print(f"\n✓  All outputs saved to: {out_dir}")
    print("  Embed best_params.json values into paper Table VI.")


if __name__ == "__main__":
    main()
