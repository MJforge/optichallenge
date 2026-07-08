"""Benchmark myalgorithm.algorithm over all problem instances.

Usage:
    python benchmark.py [timelimit]

Writes a CSV (benchmark_results.csv) and prints a markdown table sorted by
the instance's internal name.
"""
import json
import glob
import os
import sys
import time
import csv

from myalgorithm import algorithm
from utils import check_feasibility

TIMELIMIT = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
INSTANCE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _name_key(name: str):
    # sort prob_1, prob_2, ... numerically when possible
    tail = name.split("_")[-1]
    return (0, int(tail)) if tail.isdigit() else (1, name)


def main():
    files = glob.glob(os.path.join(INSTANCE_DIR, "prob_*.json"))
    entries = []
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        entries.append((f, d))
    entries.sort(key=lambda e: _name_key(e[1].get("name", os.path.basename(e[0]))))

    rows = []
    print(f"# Benchmark  timelimit={TIMELIMIT:.0f}s  instances={len(entries)}", flush=True)
    for f, prob in entries:
        name = prob.get("name", os.path.basename(f))
        n_bays = len(prob["bays"])
        n_blocks = len(prob["blocks"])
        w = prob.get("weights", {})
        t0 = time.time()
        try:
            sol = algorithm(prob, TIMELIMIT)
            elapsed = time.time() - t0
            res = check_feasibility(prob, sol)
        except Exception as e:
            elapsed = time.time() - t0
            res = {"feasible": False, "stage": -1, "violations": [str(e)]}
        feas = bool(res.get("feasible"))
        row = {
            "file": os.path.basename(f),
            "name": name,
            "bays": n_bays,
            "blocks": n_blocks,
            "w1": w.get("w1"), "w2": w.get("w2"), "w3": w.get("w3"),
            "feasible": feas,
            "stage": res.get("stage"),
            "objective": res.get("objective") if feas else None,
            "obj1": res.get("obj1") if feas else None,
            "obj2": res.get("obj2") if feas else None,
            "obj3": res.get("obj3") if feas else None,
            "elapsed": round(elapsed, 2),
        }
        rows.append(row)
        obj_s = f"{row['objective']:.0f}" if feas else f"INFEAS(stage={res.get('stage')})"
        print(f"  {name:10s} file={row['file']:13s} bays={n_bays} blk={n_blocks:4d} "
              f"feas={feas} obj={obj_s:>14s} "
              f"(o1={row['obj1']} o2={row['obj2']} o3={row['obj3']}) t={elapsed:.1f}s",
              flush=True)

    out_csv = os.path.join(os.path.dirname(__file__), "benchmark_results.csv")
    with open(out_csv, "w", newline="") as fh:
        wtr = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wtr.writeheader()
        wtr.writerows(rows)

    # markdown table
    print("\n## Results (markdown)\n", flush=True)
    print("| name | file | bays | blocks | feasible | objective | obj1 | obj2 | obj3 | time(s) |", flush=True)
    print("|---|---|---:|---:|:---:|---:|---:|---:|---:|---:|", flush=True)
    n_feas = 0
    for r in rows:
        n_feas += 1 if r["feasible"] else 0
        obj = f"{r['objective']:.0f}" if r["feasible"] else "—"
        o1 = f"{r['obj1']:.0f}" if r["feasible"] else "—"
        o2 = f"{r['obj2']:.0f}" if r["feasible"] else "—"
        o3 = f"{r['obj3']:.0f}" if r["feasible"] else "—"
        print(f"| {r['name']} | {r['file']} | {r['bays']} | {r['blocks']} | "
              f"{'OK' if r['feasible'] else 'FAIL'} | {obj} | {o1} | {o2} | {o3} | {r['elapsed']:.1f} |",
              flush=True)
    print(f"\nFeasible: {n_feas}/{len(rows)}   CSV: {out_csv}", flush=True)


if __name__ == "__main__":
    main()
