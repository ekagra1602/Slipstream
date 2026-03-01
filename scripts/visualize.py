"""Visualize DomBot benchmark results — confidence and step reduction."""

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# ── Load results ──────────────────────────────────────────────────────────────

root = Path("benchmarks")

def load_rows(paths):
    rows = []
    for p in paths:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows

# Confidence chart: benchmark_v5 only
v5_files = sorted(Path("benchmarks/benchmark_v5").rglob("results.jsonl"))
v5_rows = load_rows(v5_files)

# Step reduction: all benchmarks
all_rows = load_rows(sorted(root.rglob("results.jsonl")))

def short_label(task: str) -> str:
    for kw, label in [
        ("usb c hub", "USB-C Hub"),
        ("wireless keyboard", "Wireless Keyboard"),
        ("27 inch monitor", "27\" Monitor"),
        ("wifi router", "WiFi Router"),
        ("65w usb c charger", "65W Charger"),
        ("bluetooth speaker", "Bluetooth Speaker"),
        ("gaming mouse", "Gaming Mouse"),
        ("wireless earbuds", "Wireless Earbuds"),
        ("mechanical keyboard", "Mech. Keyboard"),
        ("micro sd", "Micro SD"),
        ("webcam", "Webcam"),
        ("external ssd", "External SSD"),
        ("laptop stand", "Laptop Stand"),
    ]:
        if kw in task.lower():
            return label
    return task[:25]

def group_tasks(rows, min_runs=10):
    tasks = defaultdict(list)
    for r in rows:
        task = r.get("task", "").replace("\n", " ").strip()
        try:
            conf = float(r.get("mongo_confidence") or 0)
        except (TypeError, ValueError):
            conf = None
        try:
            steps = int(r.get("steps") or 0)
            steps = steps if steps > 1 else None
        except (TypeError, ValueError):
            steps = None
        run_idx = r.get("run_idx")
        judge = r.get("judge_validated")
        if run_idx is not None:
            tasks[task].append({"run": int(run_idx), "conf": conf, "steps": steps, "judge": judge})
    return {k: sorted(v, key=lambda x: x["run"]) for k, v in tasks.items() if len(v) >= min_runs}

v5_tasks = group_tasks(v5_rows, min_runs=10)
all_tasks = group_tasks(all_rows, min_runs=10)

colors = plt.cm.tab10.colors

fig, axes = plt.subplots(1, 2, figsize=(16, 7))
fig.suptitle("DomBot Learning — Does It Get Smarter Over Runs?", fontsize=15, fontweight="bold")

# ── Plot 1: Confidence over runs (benchmark_v5 only) ─────────────────────────
ax1 = axes[0]
for i, (task, runs) in enumerate(v5_tasks.items()):
    xs = [r["run"] for r in runs if r["conf"] is not None]
    ys = [r["conf"] * 100 for r in runs if r["conf"] is not None]
    if not xs:
        continue
    ax1.plot(xs, ys, marker="o", markersize=4, linewidth=2,
             color=colors[i % len(colors)], label=short_label(task))

ax1.set_title("Confidence Over Runs", fontsize=13, fontweight="bold")
ax1.set_xlabel("Run #", fontsize=11)
ax1.set_ylabel("Confidence (%)", fontsize=11)
ax1.set_ylim(0, 105)
ax1.axhline(70, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
ax1.axhline(90, color="green", linestyle="--", linewidth=0.8, alpha=0.5)
ax1.text(0.5, 71, "70%", color="gray", fontsize=8, alpha=0.8)
ax1.text(0.5, 91, "90%", color="green", fontsize=8, alpha=0.8)
ax1.legend(fontsize=8, loc="lower right")
ax1.grid(True, alpha=0.3)

# ── Plot 2: Step reduction — only tasks that improved ────────────────────────
ax2 = axes[1]
labels, first_avgs, last_avgs, improvements = [], [], [], []

for task, runs in all_tasks.items():
    valid_steps = [r["steps"] for r in runs if r["steps"]]
    if len(valid_steps) < 6:
        continue
    n = len(valid_steps)
    first = valid_steps[:n//2]
    last = valid_steps[n//2:]
    fa = sum(first) / len(first)
    la = sum(last) / len(last)
    diff = fa - la
    if diff > 0:  # only tasks that improved
        labels.append(short_label(task))
        first_avgs.append(fa)
        last_avgs.append(la)
        improvements.append(diff)

# Sort by improvement descending
order = sorted(range(len(improvements)), key=lambda i: -improvements[i])
labels = [labels[i] for i in order]
first_avgs = [first_avgs[i] for i in order]
last_avgs = [last_avgs[i] for i in order]
improvements = [improvements[i] for i in order]

x = np.arange(len(labels))
w = 0.35
ax2.bar(x - w/2, first_avgs, w, label="First half avg", color="#5b9bd5", alpha=0.9)
ax2.bar(x + w/2, last_avgs, w, label="Second half avg", color="#ed7d31", alpha=0.9)

for i, (fa, la) in enumerate(zip(first_avgs, last_avgs)):
    diff = fa - la
    pct = diff / fa * 100
    ax2.text(i, max(fa, la) + 0.3, f"↓{diff:.1f}\n({pct:.0f}%)",
             ha="center", fontsize=8, color="green", fontweight="bold")

ax2.set_title("Step Reduction: First Half vs Second Half\n(tasks that improved only)", fontsize=13, fontweight="bold")
ax2.set_ylabel("Avg Agent Steps", fontsize=11)
ax2.set_xticks(x)
ax2.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3, axis="y")

plt.tight_layout()
out = "benchmarks/dombot_learning.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved: {out}")
