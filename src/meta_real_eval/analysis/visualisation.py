"""Visualisation helpers for thesis figures.

Call each function with aggregated result data (loaded from results/ JSON files)
and a matplotlib Axes object.  Saving and figure layout are the caller's job.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np


# ---------------------------------------------------------------------------
# RQ1: Kill-rate bar chart
# ---------------------------------------------------------------------------

def plot_kill_rates(
    kill_rates: dict[str, dict],  # {operator: {"kill_rate": float, "total": int}}
    ax: plt.Axes,
    title: str = "Kill rates by mutation operator",
) -> None:
    operators = list(kill_rates.keys())
    rates = [kill_rates[op]["kill_rate"] * 100 for op in operators]
    colors = ["#2E75B6" if op != "LLM" else "#C0392B" for op in operators]

    bars = ax.bar(operators, rates, color=colors, edgecolor="white")
    ax.set_ylabel("Kill rate (%)")
    ax.set_ylim(0, 110)
    ax.set_title(title)
    ax.axhline(100, color="gray", linestyle="--", linewidth=0.8)

    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{rate:.0f}%", ha="center", va="bottom", fontsize=9)


# ---------------------------------------------------------------------------
# RQ2: Tau_b distribution box plot
# ---------------------------------------------------------------------------

def plot_tau_distribution(
    tau_values_by_model: dict[str, list[float]],
    ax: plt.Axes,
    title: str = "Kendall τ_b distribution across tasks",
) -> None:
    labels = list(tau_values_by_model.keys())
    data = [tau_values_by_model[m] for m in labels]

    ax.boxplot(data, labels=labels, notch=False, patch_artist=True)
    ax.axhline(0, color="red", linestyle="--", linewidth=0.8, label="τ_b = 0 (random)")
    ax.axhline(0.85, color="green", linestyle="--", linewidth=0.8, label="τ_b = 0.85 (stable)")
    ax.set_ylabel("Kendall τ_b")
    ax.set_title(title)
    ax.legend(fontsize=8)


# ---------------------------------------------------------------------------
# RQ4: Interaction heatmap
# ---------------------------------------------------------------------------

def plot_interaction_heatmap(
    tau_by_level_by_model: dict[str, dict[float, float]],
    ax: plt.Axes,
    title: str = "τ_b vs degradation level (interaction RQ2×RQ4)",
) -> None:
    models = list(tau_by_level_by_model.keys())
    levels = sorted(next(iter(tau_by_level_by_model.values())).keys())

    matrix = np.array([
        [tau_by_level_by_model[m].get(l, float("nan")) for l in levels]
        for m in models
    ])

    im = ax.imshow(matrix, aspect="auto", vmin=-1, vmax=1, cmap="RdYlGn")
    ax.set_xticks(range(len(levels)))
    ax.set_xticklabels([f"{int(l*100)}%" for l in levels])
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models)
    ax.set_xlabel("Degradation level")
    ax.set_title(title)
    plt.colorbar(im, ax=ax, label="τ_b")


# ---------------------------------------------------------------------------
# Convenience: save a figure
# ---------------------------------------------------------------------------

def save_figure(fig: plt.Figure, path: Path, dpi: int = 150) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
