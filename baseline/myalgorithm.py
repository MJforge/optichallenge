# myalgorithm.py
# This is a template for the custom algorithm.

from __future__ import annotations

import math
import random
import re
import time
from typing import Dict, List, Tuple, Optional, Set


def _bbox(block_data: dict, orient_idx: int) -> Tuple[float, float, float, float]:
    xs, ys = [], []
    for layer in block_data["shape"][orient_idx]["layers"]:
        for x, y in layer:
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        return (0.0, 0.0, 1.0, 1.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _fit_range(block_data: dict, orient_idx: int, bay: dict) -> Optional[Tuple[int, int, int, int, Tuple[float, float, float, float]]]:
    lx0, ly0, lx1, ly1 = _bbox(block_data, orient_idx)
    W, H = float(bay["width"]), float(bay["height"])
    x_low = math.ceil(-lx0)
    x_high = math.floor(W - lx1)
    y_low = math.ceil(-ly0)
    y_high = math.floor(H - ly1)
    if x_low > x_high or y_low > y_high:
        return None
    return int(max(0, x_low)), int(x_high), int(max(0, y_low)), int(y_high), (lx0, ly0, lx1, ly1)


def _world_rect(x: int, y: int, bb: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    lx0, ly0, lx1, ly1 = bb
    return (x + lx0, y + ly0, x + lx1, y + ly1)


def _rect_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float], eps: float = 1e-9) -> bool:
    return not (a[2] <= b[0] + eps or b[2] <= a[0] + eps or a[3] <= b[1] + eps or b[3] <= a[1] + eps)


def _time_overlap(a1: int, e1: int, a2: int, e2: int) -> bool:
    return a1 < e2 and a2 < e1


def _first_valid_position(
    block_data: dict,
    orient_idx: int,
    bay: dict,
    active_rects: List[Tuple[float, float, float, float]],
    max_candidates: int = 120,
) -> Optional[Tuple[int, int, float]]:
    """Bottom-left style placement using rectangle non-overlap as a fast filter."""
    fit = _fit_range(block_data, orient_idx, bay)
    if fit is None:
        return None
    x_low, x_high, y_low, y_high, bb = fit
    lx0, ly0, lx1, ly1 = bb

    xs = {x_low}
    ys = {y_low}
    for r in active_rects:
        # Put new left edge on old right edge, or new bottom edge on old top edge.
        xs.add(int(math.ceil(r[2] - lx0)))
        ys.add(int(math.ceil(r[3] - ly0)))
        # Also try near left/bottom edges. Sometimes this helps with irregular bboxes.
        xs.add(int(math.ceil(r[0] - lx1)))
        ys.add(int(math.ceil(r[1] - ly1)))

    xs = [x for x in xs if x_low <= x <= x_high]
    ys = [y for y in ys if y_low <= y <= y_high]

    # Bottom-left priority: lower y first, then lower x. Limit candidates for speed.
    tried = 0
    best = None
    for y in sorted(ys):
        for x in sorted(xs):
            tried += 1
            if tried > max_candidates:
                break
            wr = _world_rect(x, y, bb)
            if any(_rect_overlap(wr, old) for old in active_rects):
                continue
            # lower top edge and lower right edge = tighter packing
            score = wr[3] * 1000.0 + wr[2]
            cand = (score, x, y)
            if best is None or cand < best:
                best = cand
        if tried > max_candidates:
            break

    if best is None:
        return None
    score, x, y = best
    return int(x), int(y), float(score)

def _build_operations(assignments: List[dict]) -> dict:
    buckets: Dict[int, List[Tuple[int, int, dict]]] = {}
    for a in assignments:
        bid = int(a["block_id"])
        bay = int(a["bay_id"])
        et = int(a["entry_time"])
        xt = int(a["exit_time"])
        buckets.setdefault(xt, []).append((0, bid, {"type": "EXIT", "block_id": bid, "bay_id": bay}))
        buckets.setdefault(et, []).append((1, bid, {
            "type": "ENTRY", "block_id": bid, "bay_id": bay,
            "x": int(a["x"]), "y": int(a["y"]), "orient_idx": int(a["orient_idx"]),
        }))
    return {str(t): [op for _, _, op in sorted(buckets[t], key=lambda z: (z[0], z[1]))]
            for t in sorted(buckets)}


def _solution_from_assignments(assignments: Dict[int, dict] | List[dict]) -> dict:
    if isinstance(assignments, dict):
        rows = list(assignments.values())
    else:
        rows = assignments
    return {"operations": _build_operations(rows)}


def _assignments_from_solution(sol: dict) -> Dict[int, dict]:
    out: Dict[int, dict] = {}
    for t_str, ops in sol.get("operations", {}).items():
        t = int(t_str)
        for op in ops:
            bid = int(op["block_id"])
            if op["type"] == "ENTRY":
                out.setdefault(bid, {})
                out[bid].update({
                    "block_id": bid, "bay_id": int(op["bay_id"]),
                    "x": int(op.get("x", 0)), "y": int(op.get("y", 0)),
                    "orient_idx": int(op.get("orient_idx", 0)),
                    "entry_time": t,
                })
            elif op["type"] == "EXIT":
                out.setdefault(bid, {"block_id": bid})
                out[bid].update({"bay_id": int(op["bay_id"]), "exit_time": t})
    return out


def _make_order(blocks: List[dict], mode: str) -> List[int]:
    ids = list(range(len(blocks)))
    if mode == "edd":
        return sorted(ids, key=lambda i: (blocks[i]["due_date"], blocks[i]["release_time"], blocks[i]["processing_time"]))
    if mode == "slack":
        return sorted(ids, key=lambda i: (blocks[i]["due_date"] - blocks[i]["release_time"] - blocks[i]["processing_time"], blocks[i]["due_date"]))
    if mode == "release_edd":
        return sorted(ids, key=lambda i: (blocks[i]["release_time"], blocks[i]["due_date"], blocks[i]["processing_time"]))
    if mode == "long_first_edd":
        return sorted(ids, key=lambda i: (blocks[i]["due_date"], -blocks[i]["processing_time"], blocks[i]["release_time"]))
    if mode == "heavy_edd":
        return sorted(ids, key=lambda i: (blocks[i]["due_date"], -blocks[i]["workload"], blocks[i]["release_time"]))
    return sorted(ids, key=lambda i: (blocks[i]["due_date"], blocks[i]["release_time"]))


def _bay_weights(bays: List[dict]) -> List[float]:
    areas = [float(b["width"] * b["height"]) for b in bays]
    avg = sum(areas) / max(1, len(areas))
    return [avg / a if a > 0 else 1.0 for a in areas]


def _imbalance_after(bay_loads: List[float], bw: List[float], bay_id: int, workload: float) -> float:
    loads = bay_loads[:]
    loads[bay_id] += workload
    vals = [bw[j] * loads[j] for j in range(len(loads))]
    return max(vals) - min(vals) if vals else 0.0

def _construct_empty_bay_solution(prob_info: dict, order_mode: str = "edd", bay_bias: float = 1.0) -> dict:
    bays = prob_info["bays"]
    blocks = prob_info["blocks"]
    n_bays = len(bays)
    weights = prob_info.get("weights", {})
    w1, w2, w3 = float(weights.get("w1", 1.0)), float(weights.get("w2", 1.0)), float(weights.get("w3", 1.0))
    bw = _bay_weights(bays)

    bay_available = [0] * n_bays
    bay_loads = [0.0] * n_bays
    assignments: Dict[int, dict] = {}

    for bi in _make_order(blocks, order_mode):
        blk = blocks[bi]
        r, due, proc = int(blk["release_time"]), int(blk["due_date"]), int(blk["processing_time"])
        prefs = list(blk.get("bay_preferences", [0] * n_bays))
        smax = max(prefs) if prefs else 0
        workload = float(blk["workload"])
        best = None
        for bay_id, bay in enumerate(bays):
            for oi in range(len(blk["shape"])):
                fit = _fit_range(blk, oi, bay)
                if fit is None:
                    continue
                x_low, _, y_low, _, bb = fit
                entry = max(r, bay_available[bay_id])
                exit_t = entry + proc
                tard = max(0, exit_t - due)
                pref_pen = smax - prefs[bay_id]
                imb = _imbalance_after(bay_loads, bw, bay_id, workload)
                rect = _world_rect(x_low, y_low, bb)
                fit_score = rect[3] * 1000.0 + rect[2]
                score = w1 * tard + bay_bias * w3 * pref_pen + w2 * imb + 1e-3 * exit_t + 1e-5 * fit_score
                cand = (score, exit_t, pref_pen, bay_id, oi, x_low, y_low, entry)
                if best is None or cand < best:
                    best = cand
        if best is None:
            bay_id, oi, x, y, entry = 0, 0, 0, 0, r
            exit_t = entry + proc
        else:
            _, exit_t, _, bay_id, oi, x, y, entry = best
        assignments[bi] = {"block_id": bi, "bay_id": bay_id, "x": x, "y": y, "orient_idx": oi,
                           "entry_time": entry, "exit_time": exit_t}
        bay_available[bay_id] = int(exit_t)
        bay_loads[bay_id] += workload
    return _solution_from_assignments(assignments)

def _construct_packed_solution(prob_info: dict, order_mode: str = "edd", bay_bias: float = 1.0) -> dict:
    bays = prob_info["bays"]
    blocks = prob_info["blocks"]
    n_bays = len(bays)
    weights = prob_info.get("weights", {})
    w1, w2, w3 = float(weights.get("w1", 1.0)), float(weights.get("w2", 1.0)), float(weights.get("w3", 1.0))
    bw = _bay_weights(bays)

    assignments: Dict[int, dict] = {}
    by_bay: List[List[dict]] = [[] for _ in range(n_bays)]
    bay_loads = [0.0] * n_bays

    for bi in _make_order(blocks, order_mode):
        blk = blocks[bi]
        r, due, proc = int(blk["release_time"]), int(blk["due_date"]), int(blk["processing_time"])
        prefs = list(blk.get("bay_preferences", [0] * n_bays))
        smax = max(prefs) if prefs else 0
        workload = float(blk["workload"])
        best = None

        for bay_id, bay in enumerate(bays):
            entries = {r}
            for a in by_bay[bay_id]:
                if a["exit_time"] >= r:
                    entries.add(int(a["exit_time"]))
            entries = sorted(entries)[:50]

            for entry in entries:
                exit_t = entry + proc
                active = [a for a in by_bay[bay_id] if _time_overlap(entry, exit_t, a["entry_time"], a["exit_time"])]
                active_rects = [a["rect"] for a in active]
                for oi in range(len(blk["shape"])):
                    pos = _first_valid_position(blk, oi, bay, active_rects)
                    if pos is None:
                        continue
                    x, y, fit_score = pos
                    tard = max(0, exit_t - due)
                    pref_pen = smax - prefs[bay_id]
                    imb = _imbalance_after(bay_loads, bw, bay_id, workload)

                    score = w1 * tard + bay_bias * w3 * pref_pen + w2 * imb + 1e-3 * exit_t + 1e-5 * fit_score
                    cand = (score, tard, exit_t, pref_pen, fit_score, bay_id, oi, x, y, entry)
                    if best is None or cand < best:
                        best = cand

        if best is None:

            tmp_sol = _construct_empty_bay_solution(prob_info, order_mode="edd")
            return tmp_sol

        _, _, exit_t, _, _, bay_id, oi, x, y, entry = best
        bb = _bbox(blk, oi)
        row = {"block_id": bi, "bay_id": bay_id, "x": x, "y": y, "orient_idx": oi,
               "entry_time": entry, "exit_time": exit_t, "rect": _world_rect(x, y, bb)}
        assignments[bi] = {k: v for k, v in row.items() if k != "rect"}
        by_bay[bay_id].append(row)
        bay_loads[bay_id] += workload

    return _solution_from_assignments(assignments)

def _check(prob_info: dict, sol: dict) -> Tuple[bool, float, dict]:
    try:
        from utils import check_feasibility
        res = check_feasibility(prob_info, sol)
        if res.get("feasible"):
            return True, float(res.get("objective", float("inf"))), res
        return False, float("inf"), res
    except Exception as e:
        return False, float("inf"), {"feasible": False, "stage": -1, "violations": [str(e)]}


def _violating_ids(result: dict, n_blocks: int) -> Set[int]:
    ids: Set[int] = set()
    for msg in result.get("violations", [])[:80]:
        for m in re.finditer(r"block\s+(\d+)", str(msg)):
            bid = int(m.group(1))
            if 0 <= bid < n_blocks:
                ids.add(bid)
    return ids


def _empty_entry(existing: List[dict], release: int, proc: int) -> int:
    entry = int(release)
    changed = True
    while changed:
        changed = False
        exit_t = entry + proc
        for a in existing:
            if _time_overlap(entry, exit_t, int(a["entry_time"]), int(a["exit_time"])):
                entry = max(entry, int(a["exit_time"]))
                changed = True
    return entry


def _force_one_empty(prob_info: dict, assignments: Dict[int, dict], bid: int) -> None:
    """Move one block to an empty interval in the best scoring bay."""
    bays = prob_info["bays"]
    blocks = prob_info["blocks"]
    blk = blocks[bid]
    n_bays = len(bays)
    weights = prob_info.get("weights", {})
    w1, w2, w3 = float(weights.get("w1", 1.0)), float(weights.get("w2", 1.0)), float(weights.get("w3", 1.0))
    bw = _bay_weights(bays)

    # Current loads without this block.
    bay_loads = [0.0] * n_bays
    by_bay = [[] for _ in range(n_bays)]
    for k, a in assignments.items():
        if k == bid:
            continue
        by_bay[int(a["bay_id"])].append(a)
        bay_loads[int(a["bay_id"])] += float(blocks[k]["workload"])

    r, due, proc = int(blk["release_time"]), int(blk["due_date"]), int(blk["processing_time"])
    workload = float(blk["workload"])
    prefs = list(blk.get("bay_preferences", [0] * n_bays))
    smax = max(prefs) if prefs else 0

    best = None
    for bay_id, bay in enumerate(bays):
        existing = by_bay[bay_id]
        entry = _empty_entry(existing, r, proc)
        exit_t = entry + proc
        for oi in range(len(blk["shape"])):
            fit = _fit_range(blk, oi, bay)
            if fit is None:
                continue
            x, _, y, _, bb = fit
            tard = max(0, exit_t - due)
            pref_pen = smax - prefs[bay_id]
            imb = _imbalance_after(bay_loads, bw, bay_id, workload)
            rect = _world_rect(x, y, bb)
            fit_score = rect[3] * 1000.0 + rect[2]
            score = w1 * tard + w3 * pref_pen + w2 * imb + 1e-3 * exit_t + 1e-5 * fit_score
            cand = (score, exit_t, pref_pen, bay_id, oi, x, y, entry)
            if best is None or cand < best:
                best = cand

    if best is None:
        assignments[bid] = {"block_id": bid, "bay_id": 0, "x": 0, "y": 0, "orient_idx": 0,
                            "entry_time": r, "exit_time": r + proc}
    else:
        _, exit_t, _, bay_id, oi, x, y, entry = best
        assignments[bid] = {"block_id": bid, "bay_id": bay_id, "x": x, "y": y, "orient_idx": oi,
                            "entry_time": entry, "exit_time": exit_t}


def _repair_to_feasible(prob_info: dict, sol: dict, time_deadline: float, max_rounds: int = 20) -> dict:
    n_blocks = len(prob_info["blocks"])
    assignments = _assignments_from_solution(sol)

    for bid in range(n_blocks):
        if bid not in assignments or "entry_time" not in assignments[bid] or "exit_time" not in assignments[bid]:
            _force_one_empty(prob_info, assignments, bid)

    seen_bad: Dict[int, int] = {}
    for _ in range(max_rounds):
        if time.time() > time_deadline:
            break
        sol2 = _solution_from_assignments(assignments)
        feasible, _, result = _check(prob_info, sol2)
        if feasible:
            return sol2
        bad = _violating_ids(result, n_blocks)
        if not bad:
            break
        ordered_bad = sorted(bad, key=lambda b: (seen_bad.get(b, 0), prob_info["blocks"][b]["due_date"]))
        for bid in ordered_bad:
            seen_bad[bid] = seen_bad.get(bid, 0) + 1
            _force_one_empty(prob_info, assignments, bid)
    return _solution_from_assignments(assignments)


def _bay_feasible(bay, rows: List[dict], blks: List, blocks_data: List[dict]) -> bool:
    """Check feasibility of a SINGLE bay given its assignment rows.

    Mirrors utils.check_feasibility stages 2-5 restricted to one bay.  This is
    valid because blocks in different bays never interact, so a move that only
    touches one bay can be validated by re-checking that bay alone.

    rows/blks are parallel lists (blks[i] is the Block for rows[i]).
    """
    from utils import check_entry, check_exit, check_collisions
    n = len(rows)

    # -- Stage 4a: bay boundary ------------------------------------------------
    for b in blks:
        if not bay.contains_block(b):
            return False

    # -- Stage 4b: pairwise spatial collisions among time-overlapping blocks ---
    for p in range(n):
        ap = rows[p]
        for q in range(p + 1, n):
            aq = rows[q]
            if not (ap["entry_time"] < aq["exit_time"] and aq["entry_time"] < ap["exit_time"]):
                continue
            if check_collisions(bay, [blks[p], blks[q]]):
                return False

    # -- Stage 2: crane entry --------------------------------------------------
    for idx in range(n):
        ai = rows[idx]["entry_time"]
        present = [blks[k] for k in range(n)
                   if k != idx and rows[k]["entry_time"] < ai < rows[k]["exit_time"]]
        if check_entry(bay, present, blks[idx], fast=True):
            return False

    # -- Stage 3: crane exit ---------------------------------------------------
    for idx in range(n):
        ei = rows[idx]["exit_time"]
        present = [blks[k] for k in range(n)
                   if k == idx or (rows[k]["entry_time"] < ei < rows[k]["exit_time"])]
        if check_exit(bay, present, blks[idx], fast=True):
            return False

    # -- Stage 5: sequential replay (EXIT before ENTRY at each time point) ------
    events = []
    for i, r in enumerate(rows):
        events.append((r["exit_time"], 0, i))   # EXIT
        events.append((r["entry_time"], 1, i))  # ENTRY
    times = sorted({e[0] for e in events})
    by_time: Dict[int, Tuple[List[int], List[int]]] = {t: ([], []) for t in times}
    for t, typ, i in events:
        by_time[t][typ].append(i)
    present_ids: Set[int] = set()
    for t in times:
        exits, entries = by_time[t]
        for i in exits:
            if i not in present_ids:
                return False
            present = [blks[k] for k in present_ids]
            if check_exit(bay, present, blks[i], fast=True):
                return False
            present_ids.discard(i)
        for i in entries:
            present = [blks[k] for k in present_ids]
            if check_entry(bay, present, blks[i], fast=True):
                return False
            present_ids.add(i)
    return True


def _obj2_from_loads(loads: List[float], bw: List[float]) -> float:
    n = len(loads)
    if n < 2:
        return 0.0
    vals = [bw[j] * loads[j] for j in range(n)]
    return math.floor(max(abs(vals[i] - vals[j]) for i in range(n) for j in range(n) if i != j))


def _find_placement_in_bay(prob_info: dict, bay_id: int, rows_in_bay: List[dict],
                           b_row: dict, blocks_data: List[dict],
                           max_entries: int = 12) -> Optional[dict]:
    """Find a feasible placement (orient, x, y, entry) for a block in bay_id.

    Tries candidate entry times in increasing order (least tardiness first) and
    returns the first placement that keeps the bay feasible.  Position/orient do
    not affect the objective, so any feasible placement with minimal entry is fine.
    """
    from utils import Bay, Block
    bay = Bay.from_dict(prob_info["bays"][bay_id], bay_id)
    bayd = prob_info["bays"][bay_id]
    bid = b_row["block_id"]
    blk = blocks_data[bid]
    r, proc = int(blk["release_time"]), int(blk["processing_time"])

    existing_blks = [Block(block_id=a["block_id"], block_data=blocks_data[a["block_id"]],
                           x=int(round(a["x"])), y=int(round(a["y"])), orient_idx=a["orient_idx"])
                     for a in rows_in_bay]

    entries = {r}
    for a in rows_in_bay:
        if a["exit_time"] >= r:
            entries.add(int(a["exit_time"]))
    entries = sorted(entries)[:max_entries]

    for entry in entries:
        exit_t = entry + proc
        active_rects = []
        for a in rows_in_bay:
            if a["entry_time"] < exit_t and entry < a["exit_time"]:
                bb = _bbox(blocks_data[a["block_id"]], a["orient_idx"])
                active_rects.append(_world_rect(a["x"], a["y"], bb))
        for oi in range(len(blk["shape"])):
            pos = _first_valid_position(blk, oi, bayd, active_rects)
            if pos is None:
                continue
            x, y, _ = pos
            cand = dict(b_row, bay_id=bay_id, x=int(x), y=int(y), orient_idx=oi,
                        entry_time=int(entry), exit_time=int(exit_t))
            cand_blk = Block(block_id=bid, block_data=blk, x=int(x), y=int(y), orient_idx=oi)
            if _bay_feasible(bay, rows_in_bay + [cand], existing_blks + [cand_blk], blocks_data):
                return cand
    return None


def _local_search(prob_info: dict, assignments: Dict[int, dict], deadline: float) -> Dict[int, dict]:
    """Improve a feasible solution by relocating blocks to better bays.

    obj2 (imbalance) and obj3 (preference) depend only on bay assignment, so we
    try relocating each block to another bay, accepting a move only when the
    total weighted objective strictly improves and the target bay stays feasible.
    Moving a block OUT of a bay can never break that bay (fewer constraints), so
    only the target bay needs re-validation.
    """
    blocks = prob_info["blocks"]
    bays = prob_info["bays"]
    n_bays = len(bays)
    if n_bays < 2:
        return assignments
    weights = prob_info.get("weights", {})
    w1 = float(weights.get("w1", 1.0))
    w2 = float(weights.get("w2", 1.0))
    w3 = float(weights.get("w3", 1.0))
    bw = _bay_weights(bays)

    def loads() -> List[float]:
        L = [0.0] * n_bays
        for bid, a in assignments.items():
            L[a["bay_id"]] += float(blocks[bid]["workload"])
        return L

    def prefs_of(bid: int) -> List[float]:
        return list(blocks[bid].get("bay_preferences", [0] * n_bays))

    def rows_of_bay(tb: int, exclude: Optional[int] = None) -> List[dict]:
        return [assignments[k] for k in assignments
                if assignments[k]["bay_id"] == tb and k != exclude]

    L = loads()
    cur_obj2 = _obj2_from_loads(L, bw)

    def try_relocations() -> bool:
        nonlocal L, cur_obj2
        any_move = False
        order = sorted(assignments.keys(),
                       key=lambda b: -(max(prefs_of(b)) - prefs_of(b)[assignments[b]["bay_id"]]))
        for bid in order:
            if time.time() >= deadline:
                break
            a = assignments[bid]
            prefs = prefs_of(bid)
            cur_bay = a["bay_id"]
            due = int(blocks[bid]["due_date"])
            wl = float(blocks[bid]["workload"])
            cur_tard = max(0, a["exit_time"] - due)
            best_cand = None
            best_delta = -1e-9
            for tb in range(n_bays):
                if tb == cur_bay:
                    continue
                d3 = prefs[cur_bay] - prefs[tb]
                L2 = L[:]
                L2[cur_bay] -= wl
                L2[tb] += wl
                d2 = _obj2_from_loads(L2, bw) - cur_obj2
                if w2 * d2 + w3 * d3 - w1 * cur_tard >= best_delta:
                    continue
                cand = _find_placement_in_bay(prob_info, tb, rows_of_bay(tb), a, blocks)
                if cand is None:
                    continue
                d1 = max(0, cand["exit_time"] - due) - cur_tard
                delta = w1 * d1 + w2 * d2 + w3 * d3
                if delta < best_delta:
                    best_delta = delta
                    best_cand = cand
            if best_cand is not None:
                assignments[bid] = best_cand
                L = loads()
                cur_obj2 = _obj2_from_loads(L, bw)
                any_move = True
        return any_move

    def try_swaps(max_partners: int = 12) -> bool:
        nonlocal L, cur_obj2
        any_move = False
        order = sorted(assignments.keys(),
                       key=lambda b: -(max(prefs_of(b)) - prefs_of(b)[assignments[b]["bay_id"]]))
        for i in order:
            if time.time() >= deadline:
                break
            ai = assignments[i]
            A = ai["bay_id"]
            prefs_i = prefs_of(i)
            tgt = max(range(n_bays), key=lambda j: prefs_i[j])  # most-preferred bay
            if tgt == A or prefs_i[tgt] <= prefs_i[A]:
                continue
            due_i = int(blocks[i]["due_date"])
            wl_i = float(blocks[i]["workload"])
            tard_i = max(0, ai["exit_time"] - due_i)
            B = tgt
            # candidate partners j in bay B that tolerate/prefer moving to A
            partners = [k for k in assignments if assignments[k]["bay_id"] == B]
            partners.sort(key=lambda k: -(prefs_of(k)[A] - prefs_of(k)[B]))
            best = None
            best_delta = -1e-9
            for j in partners[:max_partners]:
                if time.time() >= deadline:
                    break
                aj = assignments[j]
                prefs_j = prefs_of(j)
                due_j = int(blocks[j]["due_date"])
                wl_j = float(blocks[j]["workload"])
                tard_j = max(0, aj["exit_time"] - due_j)
                d3 = (prefs_i[A] - prefs_i[B]) + (prefs_j[B] - prefs_j[A])
                L2 = L[:]
                L2[A] += (wl_j - wl_i)
                L2[B] += (wl_i - wl_j)
                d2 = _obj2_from_loads(L2, bw) - cur_obj2
                if w2 * d2 + w3 * d3 - w1 * (tard_i + tard_j) >= best_delta:
                    continue
                rows_B = rows_of_bay(B, exclude=j)
                cand_i = _find_placement_in_bay(prob_info, B, rows_B, ai, blocks)
                if cand_i is None:
                    continue
                rows_A = rows_of_bay(A, exclude=i)
                cand_j = _find_placement_in_bay(prob_info, A, rows_A, aj, blocks)
                if cand_j is None:
                    continue
                d1 = (max(0, cand_i["exit_time"] - due_i) - tard_i) + \
                     (max(0, cand_j["exit_time"] - due_j) - tard_j)
                delta = w1 * d1 + w2 * d2 + w3 * d3
                if delta < best_delta:
                    best_delta = delta
                    best = (j, cand_i, cand_j)
            if best is not None:
                j, cand_i, cand_j = best
                assignments[i] = cand_i
                assignments[j] = cand_j
                L = loads()
                cur_obj2 = _obj2_from_loads(L, bw)
                any_move = True
        return any_move

    def hill_climb() -> None:
        while time.time() < deadline:
            moved = try_relocations()
            if time.time() >= deadline:
                break
            moved = try_swaps() or moved
            if not moved:
                break

    def snapshot() -> Dict[int, dict]:
        return {k: dict(v) for k, v in assignments.items()}

    def total_obj() -> float:
        LL = loads()
        o2 = _obj2_from_loads(LL, bw)
        o1 = 0.0
        o3 = 0.0
        for bid, a in assignments.items():
            o1 += max(0, a["exit_time"] - int(blocks[bid]["due_date"]))
            pr = prefs_of(bid)
            o3 += max(pr) - pr[a["bay_id"]]
        return w1 * o1 + w2 * o2 + w3 * o3

    # Phase A: descend to a local optimum.
    hill_climb()
    best_assign = snapshot()
    best_val = total_obj()

    # Phase B: ruin-and-recreate LNS to use the remaining budget and escape
    # local optima.  Ruin: relocate a random subset of blocks to a feasible
    # (possibly worse) bay.  Recreate: hill-climb again.  Keep best.
    rng = random.Random(12345)
    all_ids = list(assignments.keys())
    while time.time() < deadline and len(all_ids) > 1:
        k = max(1, int(0.10 * len(all_ids)))
        victims = rng.sample(all_ids, min(k, len(all_ids)))
        for bid in victims:
            if time.time() >= deadline:
                break
            a = assignments[bid]
            cur = a["bay_id"]
            others = [tb for tb in range(n_bays) if tb != cur]
            rng.shuffle(others)
            for tb in others:
                cand = _find_placement_in_bay(prob_info, tb, rows_of_bay(tb), a, blocks)
                if cand is not None:
                    assignments[bid] = cand
                    break
        L = loads()
        cur_obj2 = _obj2_from_loads(L, bw)
        hill_climb()
        val = total_obj()
        if val < best_val:
            best_val = val
            best_assign = snapshot()
        else:
            assignments.clear()
            assignments.update({k2: dict(v) for k2, v in best_assign.items()})
            L = loads()
            cur_obj2 = _obj2_from_loads(L, bw)

    assignments.clear()
    assignments.update(best_assign)
    return assignments


def algorithm(prob_info: dict, timelimit: float = 60) -> dict:
    # The tester may call algorithm() multiple times in one Python process.
    # Clear the geometry cache so old instances cannot make later runs slow.
    try:
        from utils import _poly_from_verts_cached
        _poly_from_verts_cached.cache_clear()
    except Exception:
        pass

    start = time.time()
    total_limit = max(1.0, float(timelimit) * 0.92)
    deadline = start + total_limit

    best_sol = None
    best_obj = float("inf")

    def consider(sol: dict) -> None:
        nonlocal best_sol, best_obj
        feasible, obj, _ = _check(prob_info, sol)
        if feasible and obj < best_obj:
            best_sol, best_obj = sol, obj

    for mode in ["edd", "slack", "release_edd"]:
        if time.time() > deadline:
            break
        consider(_construct_empty_bay_solution(prob_info, order_mode=mode, bay_bias=1.0))

    modes = ["edd", "slack", "release_edd", "long_first_edd", "heavy_edd"]
    biases = [1.0, 0.5, 2.0]
    for mode in modes:
        for bias in biases:
            if time.time() > deadline:
                break
            raw = _construct_packed_solution(prob_info, order_mode=mode, bay_bias=bias)
            feasible, obj, _ = _check(prob_info, raw)
            if feasible:
                if obj < best_obj:
                    best_sol, best_obj = raw, obj
            else:
                repaired = _repair_to_feasible(prob_info, raw, time_deadline=deadline)
                consider(repaired)
        if time.time() > deadline:
            break

    if best_sol is None:
        best_sol = _construct_empty_bay_solution(prob_info, order_mode="edd", bay_bias=1.0)

    # Local-search improvement phase: use the remaining time budget to relocate
    # blocks toward preferred / less-loaded bays (targets obj2 + obj3).
    if best_sol is not None and time.time() < deadline:
        assignments = _assignments_from_solution(best_sol)
        assignments = _local_search(prob_info, assignments, deadline)
        improved_sol = _solution_from_assignments(assignments)
        feasible, obj, _ = _check(prob_info, improved_sol)
        if feasible and obj <= best_obj:
            best_sol, best_obj = improved_sol, obj

    return best_sol
