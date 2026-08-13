"""Opener-solver benchmark, on real boards from Eyevy's opener database.

The cases below were sampled (seeded) from
``OpenerResearch/openerdb.txt`` — 811 distinct usable boards — and hard-coded
here so runs are comparable across changes. Three families:

* ``bag7``  — empty board to a 28-cell opener over a full bag, 0 clears.
* ``bag6``  — empty board to a 24-cell opener over 6 pieces, 0 clears.
* ``clear2``— one db opener to another over 6 pieces, **2 clears**: the
  lifted-frame path, which is where the solver does its real work.

Each case records ``routes`` (count) and ``odds`` (playable, total) as a
checksum: an optimization that changes either is a behaviour change, not a
speedup. Timings split ``Bridge.routes`` (tiling + replay) from
``Bridge.odds`` (hold coverage over queue space).

    .venv/bin/python benchmarks/bench_opener.py                # run, print table
    .venv/bin/python benchmarks/bench_opener.py --save base.json
    .venv/bin/python benchmarks/bench_opener.py --compare base.json
    .venv/bin/python benchmarks/bench_opener.py --only clear2 --repeat 3

One rotation system and one descent mode per run, named as the tests name them
and defaulting the same way: ``--system srs+``, ``--mode full``. ``--mode
instant`` additionally resolves every route's gravity waits, which is what puts
the instant-descent search on the clock — nothing else asks for it.

Cases are run in a fresh subprocess each by default (``--cold``) so one case's
``lru_cache`` warmth does not pay for the next; ``--warm`` runs them all in
this process instead, which is the regime a long session actually sees.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EMPTY = "v115@vhAAgH"

# (name, start fumen, end fumen, pieces)
CASES: list[tuple[str, str, str, int]] = [
    # --- bag7: empty -> full-bag opener, 0 clears ---------------------------
    ("bag7-01", EMPTY, "v115@zgA8IeD8FeF8CeG8CeH8AeB8JeAgH", 7),
    ("bag7-02", EMPTY, "v115@4gA8DeA8CeC8CeA8DeD8AeC8AeI8AeF8JeAgH", 7),
    ("bag7-03", EMPTY, "v115@3gC8AeA8DeF8FeD8AeB8CeD8AeB8BeF8JeAgH", 7),
    ("bag7-04", EMPTY, "v115@xgB8IeA8IeA8AeD8AeA8BeI8AeH8AeB8JeAgH", 7),
    # unreachable end shapes: the search must reject them, and that costs too
    ("bag7-05", EMPTY, "v115@xgB8HeB8HeB8CeA8CeR8BeC8JeAgH", 7),
    ("bag7-06", EMPTY, "v115@pgB8HeB8HeB8HeC8CeA8CeM8BeE8JeAgH", 7),
    ("bag7-07", EMPTY, "v115@/gB8FeF8DeT8JeAgH", 7),
    ("bag7-08", EMPTY, "v115@4gB8CeA8DeB8CeA8CeE8AeL8BeE8KeAgH", 7),

    # --- bag6: empty -> 24-cell opener, 0 clears ----------------------------
    ("bag6-01", EMPTY, "v115@BhF8EeE8DeF8CeG8JeAgH", 6),
    ("bag6-02", EMPTY, "v115@9gA8IeB8BeA8BeB8AeB8AeJ8AeF8JeAgH", 6),
    ("bag6-03", EMPTY, "v115@xgB8IeA8CeA8EeA8CeB8DeC8AeE8AeC8AeD8AeB8JeAgH", 6),
    ("bag6-04", EMPTY, "v115@/gA8FeA8BeB8BeH8CeH8AeD8JeAgH", 6),
    ("bag6-05", EMPTY, "v115@FhD8EeF8AeA8AeG8AeF8JeAgH", 6),
    ("bag6-06", EMPTY, "v115@9gF8DeE8EeF8DeG8MeAgH", 6),
    ("bag6-07", EMPTY, "v115@DhB8AeE8CeH8AeE8BeB8AeA8BeA8JeAgH", 6),
    ("bag6-08", EMPTY, "v115@7gA8HeC8GeM8BeC8AeD8JeAgH", 6),

    # --- clear2: db opener -> db opener over 6 pieces, 2 clears -------------
    ("clear2-01", "v115@9gA8IeB8EeE8AeJ8AeF8JeAgH",
     "v115@0gD8EeC8GeC8EeA8AeC8BeH8AeF8JeAgH", 6),
    ("clear2-02", "v115@9gB8HeC8EeF8AeA8AeI8AeC8JeAgH",
     "v115@+gA8FeE8CeH8AeI8AeE8JeAgH", 6),
    ("clear2-03", "v115@GhD8EeI8AeH8AeC8JeAgH",
     "v115@9gE8DeE8DeG8CeH8AeC8JeAgH", 6),
    ("clear2-04", "v115@GhD8EeI8AeH8AeC8JeAgH",
     "v115@6gA8BeB8EeB8AeC8DeH8BeI8AeC8JeAgH", 6),
    ("clear2-05", "v115@9gC8GeD8EeG8CeH8AeB8JeAgH",
     "v115@9gE8DeE8DeG8CeH8AeC8JeAgH", 6),
    ("clear2-06", "v115@9gA8FeA8BeD8BeB8AeD8CeB8AeE8AeE8JeAgH",
     "v115@lgA8IeA8IeA8CeA8EeB8BeB8DeB8BeE8AeH8AeE8JeAgH", 6),
    ("clear2-07", "v115@9gA8FeA8BeD8BeB8AeD8CeB8AeE8AeE8JeAgH",
     "v115@+gA8FeE8CeH8AeI8AeE8JeAgH", 6),
    ("clear2-08", "v115@AhA8EeC8AeA8DeF8BeH8AeE8JeAgH",
     "v115@+gA8FeE8CeH8AeI8AeE8JeAgH", 6),
]


def run_case(name: str, start: str, end: str, pieces: int,
             system: str = "srs+", mode: str = "full") -> dict:
    from mino_sdk.opener.bridge import Bridge
    from mino_sdk.opener.node import Node
    from mino_sdk.pieces import SRS, SRSPlus

    rules = {"srs": SRS, "srs+": SRSPlus}[system]()
    bridge = Bridge(start=Node(start, ()), end=Node(end, ()), pieces=pieces,
                    system=rules)

    t0 = time.perf_counter()
    routes = bridge.routes()
    if mode == "instant":
        # Resolving the gravity waits is what puts the instant-descent search
        # on the clock; left alone it is never run at all.
        for route in routes:
            route.instant
    t_routes = time.perf_counter() - t0

    from mino_sdk.opener import hold as _hold
    from mino_sdk.opener.bridge import _ORDER

    t0 = time.perf_counter()
    playable, total = _hold.coverage([r.order for r in routes], _ORDER,
                                     bridge.pieces, bridge.leftover)
    t_odds = time.perf_counter() - t0

    return {
        "name": name,
        "system": system,
        "mode": mode,
        "clears": bridge.cleared_lines,
        "routes": len(routes),
        "playable": playable,
        "total": total,
        "t_routes": t_routes,
        "t_odds": t_odds,
    }


def _select(only: str | None) -> list[tuple[str, str, str, int]]:
    if not only:
        return CASES
    return [c for c in CASES if c[0].startswith(only)]


def run_warm(cases, repeat: int, system: str, mode: str) -> list[dict]:
    out = []
    for name, start, end, pieces in cases:
        runs = [run_case(name, start, end, pieces, system, mode)
                for _ in range(repeat)]
        best = min(runs, key=lambda r: r["t_routes"] + r["t_odds"])
        best["t_routes"] = statistics.median(r["t_routes"] for r in runs)
        best["t_odds"] = statistics.median(r["t_odds"] for r in runs)
        out.append(best)
        _print_row(best)
    return out


def run_cold(cases, repeat: int, system: str, mode: str) -> list[dict]:
    out = []
    for name, _, _, _ in cases:
        runs = []
        for _ in range(repeat):
            proc = subprocess.run(
                [sys.executable, os.path.abspath(__file__), "--case", name,
                 "--system", system, "--mode", mode],
                capture_output=True, text=True, check=True,
            )
            runs.append(json.loads(proc.stdout))
        best = dict(runs[0])
        best["t_routes"] = statistics.median(r["t_routes"] for r in runs)
        best["t_odds"] = statistics.median(r["t_odds"] for r in runs)
        out.append(best)
        _print_row(best)
    return out


def _print_row(r: dict) -> None:
    total = r["t_routes"] + r["t_odds"]
    print(f"{r['name']:<11} clears={r['clears']}  routes={r['routes']:>5}  "
          f"cover={r['playable']:>4}/{r['total']}  "
          f"solve={r['t_routes']:7.3f}s  hold={r['t_odds']:6.3f}s  "
          f"total={total:7.3f}s", flush=True)


def compare(results: list[dict], path: str) -> None:
    saved = json.load(open(path))
    base = {r["name"]: r for r in saved["results"]}
    print("\n--- vs baseline -------------------------------------------------")
    ours = (results[0].get("system"), results[0].get("mode"))
    theirs = (saved.get("system", "srs+"), saved.get("mode", "full"))
    if ours != theirs:
        print(f"!! baseline was {theirs[0]}/{theirs[1]} descent, this run is "
              f"{ours[0]}/{ours[1]} — the times are not comparable")
    drift = []
    for r in results:
        b = base.get(r["name"])
        if b is None:
            print(f"{r['name']:<11} (new case, no baseline)")
            continue
        if (b["routes"], b["playable"], b["total"]) != (
                r["routes"], r["playable"], r["total"]):
            drift.append(r["name"])
            print(f"{r['name']:<11} *** RESULT CHANGED: "
                  f"routes {b['routes']}->{r['routes']}, "
                  f"cover {b['playable']}/{b['total']}"
                  f"->{r['playable']}/{r['total']}")
        old = b["t_routes"] + b["t_odds"]
        new = r["t_routes"] + r["t_odds"]
        print(f"{r['name']:<11} {old:7.3f}s -> {new:7.3f}s  "
              f"({old / new if new else float('inf'):5.2f}x)")
    old_total = sum(base[r["name"]]["t_routes"] + base[r["name"]]["t_odds"]
                    for r in results if r["name"] in base)
    new_total = sum(r["t_routes"] + r["t_odds"]
                    for r in results if r["name"] in base)
    print(f"{'TOTAL':<11} {old_total:7.3f}s -> {new_total:7.3f}s  "
          f"({old_total / new_total if new_total else float('inf'):5.2f}x)")
    if drift:
        print(f"\n!! {len(drift)} case(s) changed results — not a pure speedup: "
              + ", ".join(drift))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="case-name prefix, e.g. bag7 / clear2")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--warm", action="store_true",
                    help="run all cases in one process (shared caches)")
    ap.add_argument("--cold", action="store_true",
                    help="one subprocess per case (default)")
    ap.add_argument("--save", metavar="PATH")
    ap.add_argument("--compare", metavar="PATH")
    ap.add_argument("--system", default="srs+", choices=("srs", "srs+"),
                    help="rotation system every line is solved under "
                         "(default: srs+)")
    ap.add_argument("--mode", default="full", choices=("full", "instant"),
                    help="'instant' also resolves every route's gravity "
                         "waits, which is what exercises the instant-descent "
                         "search (default: full)")
    ap.add_argument("--case", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.case:  # subprocess worker
        name, start, end, pieces = next(c for c in CASES if c[0] == args.case)
        print(json.dumps(run_case(name, start, end, pieces,
                                  args.system, args.mode)))
        return

    cases = _select(args.only)
    if not cases:
        raise SystemExit(f"no cases match {args.only!r}")
    runner = run_warm if args.warm else run_cold
    label = "warm (shared caches)" if args.warm else "cold (subprocess per case)"
    print(f"{len(cases)} cases, {args.system}, {args.mode} descent, "
          f"repeat={args.repeat}, {label}\n")

    t0 = time.perf_counter()
    results = runner(cases, args.repeat, args.system, args.mode)
    wall = time.perf_counter() - t0

    solve = sum(r["t_routes"] for r in results)
    hold = sum(r["t_odds"] for r in results)
    print(f"\n{'TOTAL':<11} solve={solve:7.3f}s  hold={hold:6.3f}s  "
          f"sum={solve + hold:7.3f}s  (wall {wall:.1f}s)")

    if args.save:
        with open(args.save, "w") as fh:
            json.dump({"warm": bool(args.warm), "repeat": args.repeat,
                       "system": args.system, "mode": args.mode,
                       "results": results}, fh, indent=2)
        print(f"saved -> {args.save}")
    if args.compare:
        compare(results, args.compare)


if __name__ == "__main__":
    main()
