"""
رسم الرسمين البيانيين للتقرير من eval/results/summary.json (errors_per_100).

المخرجات: eval/results/chart_errors_per_100.png و chart_error_categories.png
الرسم 1: مجموع الأخطاء لكل 100 وحدة لكل نظام. الرسم 2: الأخطاء حسب النوع.
القيم في summary.json بصيغة {"mean": .., "sd": ..} (build_summary.py)، ويُرسم المتوسط.
(التسميات بالإنجليزية عمدًا، لأن matplotlib يكسر شكل الحروف العربية.)
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SYSTEMS = ["mt", "llm", "mowatin"]  # = معرّفات summary.json
NAMES = {"mt": "Generic MT (Google)", "llm": "Same LLM, no Muwattin", "mowatin": "Muwattin"}
COLORS = {"mt": "#9aa5a1", "llm": "#d9b865", "mowatin": "#17796b"}
CATS = ["quran", "hadith", "term", "ruling", "referral"]
CAT_NAMES = {"quran": "Quran", "hadith": "Hadith", "term": "Term", "ruling": "Ruling", "referral": "Referral"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--summary", default="eval/results/summary.json")
    p.add_argument("--std", type=float, default=0.0)
    p.add_argument("--outdir", default="eval/results")
    a = p.parse_args()

    raw = json.loads(Path(a.summary).read_text(encoding="utf-8"))["errors_per_100"]
    # build_summary writes {"mean", "sd"} per category; a plain number is accepted too.
    e = {s: {c: (v["mean"] if isinstance(v, dict) else v) for c, v in cats.items() if v is not None}
         for s, cats in raw.items()}
    systems = [s for s in SYSTEMS if e.get(s)]
    if not systems:
        raise SystemExit("errors_per_100 فارغ في summary.json؛ شغّلي build_summary.py أولًا")
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 4))
    tot = [sum(e[s].values()) for s in systems]
    bars = ax.bar([NAMES[s] for s in systems], tot, color=[COLORS[s] for s in systems],
                  yerr=[a.std if s == "mowatin" else 0 for s in systems], capsize=5)
    for b, v in zip(bars, tot):
        ax.text(b.get_x() + b.get_width() / 2, v + max(tot) * 0.02, f"{v:.1f}", ha="center")
    ax.set_ylabel("Errors per 100 units")
    ax.set_title("Total errors per 100 units (automatic metrics)")
    plt.xticks(rotation=12)
    fig.tight_layout()
    fig.savefig(out / "chart_errors_per_100.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4))
    w = 0.8 / len(systems)
    for k, s in enumerate(systems):
        ax.bar([i + k * w for i in range(len(CATS))], [e[s].get(c, 0) for c in CATS], w, label=NAMES[s], color=COLORS[s])
    ax.set_xticks([i + w * (len(systems) - 1) / 2 for i in range(len(CATS))])
    ax.set_xticklabels([CAT_NAMES[c] for c in CATS])
    ax.set_ylabel("Errors per 100 units")
    ax.set_title("Errors by category")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "chart_error_categories.png", dpi=200)
    plt.close(fig)
    print("تم: chart_errors_per_100.png و chart_error_categories.png")


if __name__ == "__main__":
    main()
