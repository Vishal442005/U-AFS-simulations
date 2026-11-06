#!/usr/bin/env python3
"""
render_significant_plots.py
---------------------------
Generates publication-quality vector PDF and 300 DPI PNG plots:
  1. fig1_sota_reference_distributions.pdf / .png
  2. fig2_station_density_scaling.pdf / .png
  3. fig3_traffic_mix_tradeoffs.pdf / .png
  4. fig4_deadline_sensitivity_breakdown.pdf / .png
  5. fig5_operational_envelope_heatmap.pdf / .png
  6. fig6_multimetric_pareto_frontier.pdf / .png
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import griddata

RESULTS_DIR = Path("Uafs_updated_significant/results")
FIGS_DIR = Path("Uafs_updated_significant/figures")
FIGS_DIR.mkdir(parents=True, exist_ok=True)

# Styling palette
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "grid.alpha": 0.35,
    "grid.linestyle": ":",
})

PALETTE = {
    "proposed": "#1f77b4",     # Primary Deep Blue
    "lsdsf": "#2ca02c",        # Green
    "lyapunov": "#ff7f0e",     # Orange
    "exp_rule": "#9467bd",     # Purple
    "m_lwdf": "#8c564b",       # Brown
    "edf": "#d62728",          # Crimson Red
    "edca": "#e377c2",         # Pink
    "service_drr": "#7f7f7f",  # Gray
    "round_robin": "#bcbd22",  # Olive
}

LABELS = {
    "proposed": "U-AFS (Proposed)",
    "lsdsf": "LSDSF (MobiHoc '24)",
    "lyapunov": "Lyapunov (ToN '24)",
    "exp_rule": "EXP-Rule",
    "m_lwdf": "M-LWDF",
    "edf": "EDF",
    "edca": "IEEE 802.11e EDCA",
    "service_drr": "Service-DRR",
    "round_robin": "Round-Robin",
}

def plot_fig1_sota_distributions():
    df = pd.read_csv(RESULTS_DIR / "sota_reference_benchmark.csv")
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    
    policies = ["proposed", "lsdsf", "lyapunov", "exp_rule", "edf", "service_drr"]
    data_miss = [df[df["policy"] == p]["rt_miss_fraction"] * 100.0 for p in policies]
    data_p99 = [df[df["policy"] == p]["rt_p99_ms"] for p in policies]
    data_gp = [df[df["policy"] == p]["bg_goodput_mbps"] for p in policies]
    data_fair = [df[df["policy"] == p]["service_jain"] for p in policies]
    
    col_list = [PALETTE[p] for p in policies]
    x_labels = [LABELS[p] for p in policies]
    x_pos = np.arange(len(policies))

    # (a) RT Miss Fraction
    ax = axes[0, 0]
    bars = ax.bar(x_pos, [d.mean() for d in data_miss], yerr=[d.sem()*1.96 for d in data_miss],
                  capsize=4, color=col_list, alpha=0.85, edgecolor='black', linewidth=0.8)
    ax.set_ylabel("RT Deadline Miss (%)")
    ax.set_title("(a) Real-Time Deadline Miss Fraction")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, rotation=25, ha="right")
    ax.grid(True, axis="y")
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 1.2, f"{yval:.1f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')

    # (b) RT p99 Delay
    ax = axes[0, 1]
    bars = ax.bar(x_pos, [d.mean() for d in data_p99], yerr=[d.sem()*1.96 for d in data_p99],
                  capsize=4, color=col_list, alpha=0.85, edgecolor='black', linewidth=0.8)
    ax.set_ylabel("99th-Percentile Delay (ms)")
    ax.set_title("(b) Tail Real-Time Delay (p99)")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, rotation=25, ha="right")
    ax.grid(True, axis="y")
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, f"{yval:.1f}ms", ha='center', va='bottom', fontsize=9)

    # (c) Background Goodput
    ax = axes[1, 0]
    bars = ax.bar(x_pos, [d.mean() for d in data_gp], yerr=[d.sem()*1.96 for d in data_gp],
                  capsize=4, color=col_list, alpha=0.85, edgecolor='black', linewidth=0.8)
    ax.set_ylabel("Background Goodput (Mbps)")
    ax.set_title("(c) Elastic Bulk Traffic Goodput")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, rotation=25, ha="right")
    ax.grid(True, axis="y")
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.3, f"{yval:.1f}M", ha='center', va='bottom', fontsize=9)

    # (d) Service Jain's Index
    ax = axes[1, 1]
    bars = ax.bar(x_pos, [d.mean() for d in data_fair], yerr=[d.sem()*1.96 for d in data_fair],
                  capsize=4, color=col_list, alpha=0.85, edgecolor='black', linewidth=0.8)
    ax.set_ylabel("Jain's Fairness Index")
    ax.set_title("(d) Inter-Station Service Equity")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, rotation=25, ha="right")
    ax.set_ylim(0.70, 1.02)
    ax.grid(True, axis="y")
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.01, f"{yval:.3f}", ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    fig.savefig(FIGS_DIR / "fig1_sota_reference_distributions.pdf", bbox_inches="tight")
    fig.savefig(FIGS_DIR / "fig1_sota_reference_distributions.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("Rendered fig1_sota_reference_distributions")

def plot_fig2_station_density():
    df = pd.read_csv(RESULTS_DIR / "station_density_scaling.csv")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))
    
    policies = ["proposed", "lsdsf", "lyapunov", "exp_rule", "edf", "service_drr"]
    markers = {"proposed": "o", "lsdsf": "s", "lyapunov": "^", "exp_rule": "D", "edf": "v", "service_drr": "x"}
    
    stations = sorted(df["stations"].unique())
    
    for pol in policies:
        sub = df[df["policy"] == pol]
        means_miss = [sub[sub["stations"] == n]["rt_miss_fraction"].mean() * 100.0 for n in stations]
        sems_miss = [sub[sub["stations"] == n]["rt_miss_fraction"].sem() * 100.0 * 1.96 for n in stations]
        
        means_gp = [sub[sub["stations"] == n]["bg_goodput_mbps"].mean() for n in stations]
        sems_gp = [sub[sub["stations"] == n]["bg_goodput_mbps"].sem() * 1.96 for n in stations]
        
        lw = 2.4 if pol == "proposed" else 1.6
        zorder = 5 if pol == "proposed" else 3
        
        ax1.errorbar(stations, means_miss, yerr=sems_miss, label=LABELS[pol],
                     color=PALETTE[pol], marker=markers[pol], markersize=6, linewidth=lw, capsize=3, zorder=zorder)
        ax2.errorbar(stations, means_gp, yerr=sems_gp, label=LABELS[pol],
                     color=PALETTE[pol], marker=markers[pol], markersize=6, linewidth=lw, capsize=3, zorder=zorder)
        
    ax1.set_xlabel("Number of Client Stations ($N$)")
    ax1.set_ylabel("RT Deadline Miss Fraction (%)")
    ax1.set_title("(a) Scalability: Deadline Miss Rate")
    ax1.set_xticks(stations)
    ax1.grid(True)
    ax1.legend(loc="upper left", framealpha=0.9)
    
    # Highlight saturation threshold
    ax1.axvline(16, color="gray", linestyle="--", alpha=0.7)
    ax1.text(16.5, 45, "Contention Knee\n($CW$ exhaustion)", color="gray", fontsize=9, fontstyle="italic")

    ax2.set_xlabel("Number of Client Stations ($N$)")
    ax2.set_ylabel("Background Goodput (Mbps)")
    ax2.set_title("(b) Scalability: Background Goodput")
    ax2.set_xticks(stations)
    ax2.grid(True)
    
    plt.tight_layout()
    fig.savefig(FIGS_DIR / "fig2_station_density_scaling.pdf", bbox_inches="tight")
    fig.savefig(FIGS_DIR / "fig2_station_density_scaling.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("Rendered fig2_station_density_scaling")

def plot_fig3_traffic_mix():
    df = pd.read_csv(RESULTS_DIR / "traffic_mix_heterogeneity.csv")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8))
    
    mixes = ["RT_Heavy_80_20", "Balanced_50_50", "Bulk_Heavy_20_80"]
    mix_labels = ["80% RT / 20% Bulk\n(RT-Heavy)", "50% RT / 50% Bulk\n(Balanced)", "20% RT / 80% Bulk\n(Bulk-Heavy)"]
    policies = ["proposed", "lsdsf", "lyapunov", "exp_rule", "edf", "service_drr"]
    
    x = np.arange(len(mixes))
    width = 0.13
    
    for i, pol in enumerate(policies):
        offsets = x + (i - len(policies)/2.0 + 0.5) * width
        means_miss = [df[(df["policy"] == pol) & (df["traffic_mix"] == m)]["rt_miss_fraction"].mean() * 100.0 for m in mixes]
        means_gp = [df[(df["policy"] == pol) & (df["traffic_mix"] == m)]["bg_goodput_mbps"].mean() for m in mixes]
        
        ax1.bar(offsets, means_miss, width, label=LABELS[pol], color=PALETTE[pol], alpha=0.85, edgecolor='black', linewidth=0.6)
        ax2.bar(offsets, means_gp, width, label=LABELS[pol], color=PALETTE[pol], alpha=0.85, edgecolor='black', linewidth=0.6)
        
    ax1.set_xticks(x)
    ax1.set_xticklabels(mix_labels)
    ax1.set_ylabel("RT Deadline Miss (%)")
    ax1.set_title("(a) Deadline Miss Rate Under Mix Skews")
    ax1.grid(True, axis="y")
    ax1.legend(loc="upper left", framealpha=0.9, ncol=2)

    ax2.set_xticks(x)
    ax2.set_xticklabels(mix_labels)
    ax2.set_ylabel("Background Goodput (Mbps)")
    ax2.set_title("(b) Background Goodput Under Mix Skews")
    ax2.grid(True, axis="y")

    plt.tight_layout()
    fig.savefig(FIGS_DIR / "fig3_traffic_mix_tradeoffs.pdf", bbox_inches="tight")
    fig.savefig(FIGS_DIR / "fig3_traffic_mix_tradeoffs.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("Rendered fig3_traffic_mix_tradeoffs")

def plot_fig4_deadline_sensitivity():
    df = pd.read_csv(RESULTS_DIR / "deadline_tightness_sweep.csv")
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    
    deadlines = sorted(df["deadline_ms"].unique())
    policies = ["proposed", "lsdsf", "lyapunov", "exp_rule", "edf", "service_drr"]
    markers = {"proposed": "o", "lsdsf": "s", "lyapunov": "^", "exp_rule": "D", "edf": "v", "service_drr": "x"}
    
    for pol in policies:
        sub = df[df["policy"] == pol]
        means = [sub[sub["deadline_ms"] == d]["rt_miss_fraction"].mean() * 100.0 for d in deadlines]
        sems = [sub[sub["deadline_ms"] == d]["rt_miss_fraction"].sem() * 100.0 * 1.96 for d in deadlines]
        lw = 2.4 if pol == "proposed" else 1.6
        zorder = 5 if pol == "proposed" else 3
        ax.errorbar(deadlines, means, yerr=sems, label=LABELS[pol],
                    color=PALETTE[pol], marker=markers[pol], markersize=6, linewidth=lw, capsize=3, zorder=zorder)
        
    ax.set_xlabel("Relative Delay Deadline $D$ (ms)")
    ax.set_ylabel("RT Deadline Miss Fraction (%)")
    ax.set_title("Sensitivity to Delay Deadline Tightness ($D = 10$ to $50$ ms)")
    ax.set_xticks(deadlines)
    ax.grid(True)
    ax.legend(loc="upper right", framealpha=0.9)
    
    # Knee annotation
    ax.annotate("Physical Delay Knee\n($D \\approx \\text{p99 delay}$)", xy=(15, 25), xytext=(22, 45),
                arrowprops=dict(facecolor='black', shrink=0.08, width=1.2, headwidth=6),
                fontsize=9, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.3))

    plt.tight_layout()
    fig.savefig(FIGS_DIR / "fig4_deadline_sensitivity_breakdown.pdf", bbox_inches="tight")
    fig.savefig(FIGS_DIR / "fig4_deadline_sensitivity_breakdown.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("Rendered fig4_deadline_sensitivity_breakdown")

def plot_fig5_operational_envelope():
    df = pd.read_csv(RESULTS_DIR / "operational_envelope_2d.csv")
    fig, ax = plt.subplots(figsize=(8.0, 5.5))
    
    # Compute relative gain of U-AFS over EDF: delta_miss = Miss(EDF) - Miss(U-AFS)
    grid_points = []
    for (rt_l, bg_l), group in df.groupby(["rt_load_factor", "bg_load_mbps"]):
        prop_miss = group[group["policy"] == "proposed"]["rt_miss_fraction"].mean() * 100.0
        edf_miss = group[group["policy"] == "edf"]["rt_miss_fraction"].mean() * 100.0
        gain = edf_miss - prop_miss
        grid_points.append({"rt_load": rt_l, "bg_mbps": bg_l, "gain": gain})
        
    gdf = pd.DataFrame(grid_points)
    
    xi = np.linspace(gdf["rt_load"].min(), gdf["rt_load"].max(), 100)
    yi = np.linspace(gdf["bg_mbps"].min(), gdf["bg_mbps"].max(), 100)
    X, Y = np.meshgrid(xi, yi)
    Z = griddata((gdf["rt_load"], gdf["bg_mbps"]), gdf["gain"], (X, Y), method='cubic')
    
    cs = ax.contourf(X, Y, Z, levels=15, cmap="Blues", alpha=0.9)
    cbar = fig.colorbar(cs, ax=ax)
    cbar.set_label("U-AFS Advantage over EDF (pp Miss Reduction)")
    
    # Draw contour line at 0 pp (parity boundary)
    ax.contour(X, Y, Z, levels=[0.0], colors="red", linestyles="--", linewidths=1.5)
    
    # Region annotations
    ax.text(0.55, 8.0, "Zone 1: Light Load\n(Parity: Miss < 1%)", color="#003366", fontsize=9, fontweight="bold")
    ax.text(1.05, 20.0, "Zone 2: Congested Mixed\n(U-AFS Sweet Spot: +12 to +18 pp)", color="#ffffff", fontsize=10, fontweight="bold")
    ax.text(1.35, 30.0, "Zone 3: Extreme Saturation\n(Controlled Trade-off)", color="#002244", fontsize=9, fontweight="bold")

    ax.set_xlabel("Normalized Real-Time Traffic Intensity ($\\lambda_{rt} / C_{rt}$)")
    ax.set_ylabel("Background Elastic Traffic Load (Mbps)")
    ax.set_title("Operational Feasibility Map: U-AFS Relative Performance Landscape")
    ax.grid(True, color="gray", alpha=0.25)
    
    plt.tight_layout()
    fig.savefig(FIGS_DIR / "fig5_operational_envelope_heatmap.pdf", bbox_inches="tight")
    fig.savefig(FIGS_DIR / "fig5_operational_envelope_heatmap.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("Rendered fig5_operational_envelope_heatmap")

def plot_fig6_pareto():
    df = pd.read_csv(RESULTS_DIR / "sota_reference_benchmark.csv")
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    
    policies = ["proposed", "lsdsf", "lyapunov", "exp_rule", "m_lwdf", "edf", "service_drr", "round_robin"]
    markers = {"proposed": "o", "lsdsf": "s", "lyapunov": "^", "exp_rule": "D", "m_lwdf": "p", "edf": "v", "service_drr": "X", "round_robin": "P"}
    
    for pol in policies:
        sub = df[df["policy"] == pol]
        x_val = sub["rt_miss_fraction"].mean() * 100.0
        y_val = sub["bg_goodput_mbps"].mean()
        x_err = sub["rt_miss_fraction"].sem() * 100.0 * 1.96
        y_err = sub["bg_goodput_mbps"].sem() * 1.96
        
        size = 130 if pol == "proposed" else 90
        zorder = 6 if pol == "proposed" else 4
        
        ax.errorbar(x_val, y_val, xerr=x_err, yerr=y_err, fmt='none', ecolor=PALETTE[pol], capsize=3, zorder=zorder-1)
        ax.scatter(x_val, y_val, label=LABELS[pol], color=PALETTE[pol], marker=markers[pol], s=size, edgecolors="black", linewidths=0.9, zorder=zorder)

    # Invert x-axis concept: ideal point is (0% miss, high goodput)
    ax.set_xlabel("RT Deadline Miss Fraction (%) [Lower is Better $\\rightarrow$]")
    ax.set_ylabel("Background Goodput (Mbps) [Higher is Better $\\rightarrow$]")
    ax.set_title("Multi-Objective Pareto Frontier: Timeliness vs. Bulk Goodput")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", framealpha=0.95, edgecolor="#CBD5E1", fontsize=9.5)
    
    # Annotate Pareto Optimal Region
    ax.axhspan(11.0, 16.0, 0.0, 0.25, color="green", alpha=0.08)
    ax.text(2, 11.5, "Optimal Operating Region\n(Low Miss + High Goodput)", color="green", fontsize=8.5, fontweight="bold")

    plt.tight_layout()
    fig.savefig(FIGS_DIR / "fig6_multimetric_pareto_frontier.pdf", bbox_inches="tight")
    fig.savefig(FIGS_DIR / "fig6_multimetric_pareto_frontier.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("Rendered fig6_multimetric_pareto_frontier")

def main():
    print("Rendering publication plots in Uafs_updated_significant/figures/...")
    plot_fig1_sota_distributions()
    plot_fig2_station_density()
    plot_fig3_traffic_mix()
    plot_fig4_deadline_sensitivity()
    plot_fig5_operational_envelope()
    plot_fig6_pareto()
    print("All publication figures successfully rendered!")

if __name__ == '__main__':
    main()
