"""Heavy engine-equivalence check for the bitboard search.

``tests/test_fastreach.py`` is the fast version that runs with the suite; this
is the one to run when the search itself has been touched. It sweeps a much
larger corpus — random stacks plus overhang-heavy ones, where tucks and spins
actually decide the answer — and compares :func:`mino_sdk.opener.fastreach.reach`
against :func:`mino_sdk.engine.reachable`, which stays the definition of correct.

One rotation system and one descent mode per run, named the same way the tests
name them and defaulting the same way (SRS+, full soft drop)::

    .venv/bin/python benchmarks/check_reach.py
    .venv/bin/python benchmarks/check_reach.py --system srs --mode instant
    .venv/bin/python benchmarks/check_reach.py --stacks 1000 --seed 12

Exits non-zero on any mismatch, so it can gate a change.
"""

from __future__ import annotations

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mino_sdk.engine import reachable                          # noqa: E402
from mino_sdk.opener.bridge import _board_from, _cells_of, _spawn_for  # noqa: E402
from mino_sdk.opener.fastreach import reach                    # noqa: E402
from mino_sdk.pieces import SRS, SRSPlus, PieceType            # noqa: E402

SYSTEMS = {"srs": SRS, "srs+": SRSPlus}

# Stacks with long flat runs and deep notches: an overhang is where a tuck or a
# kick is the only way in, so this is where a reachability bug shows up.
_SHAPES = (0b1111111100, 0b0011111111, 0b1110000111, 0b1111011111, 0b1000000001)


def corpus(count: int, seed: int) -> list[tuple]:
    rng = random.Random(seed)
    out = [(), (0b1111111110,), (0b1000000001,) * 2]
    for i in range(count):
        height = rng.randint(1, 7)
        if i % 2:  # half uniform noise, half overhang-heavy
            rows = tuple(rng.getrandbits(10) for _ in range(height))
        else:
            rows = tuple(rng.choice(_SHAPES + (rng.getrandbits(10),))
                         for _ in range(height))
        while rows and rows[-1] == 0:
            rows = rows[:-1]
        out.append(rows)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", default="srs+", choices=sorted(SYSTEMS),
                    help="rotation system to check (default: srs+)")
    ap.add_argument("--mode", default="full", choices=("full", "instant"),
                    help="descent mode (default: full)")
    ap.add_argument("--stacks", type=int, default=300)
    ap.add_argument("--seed", type=int, default=99)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    system = SYSTEMS[args.system]()
    instant = args.mode == "instant"
    stacks = corpus(args.stacks, args.seed)

    bad = 0
    for rows in stacks:
        for piece in PieceType:
            want = {}
            for p in reachable(_board_from(rows), piece, system,
                               spawn=_spawn_for(rows, piece, system),
                               instant=instant):
                cells = frozenset(_cells_of(piece, p.rotation, p.row, p.col,
                                            system))
                if cells not in want or p.spin.rank > want[cells].rank:
                    want[cells] = p.spin
            got = reach(rows, piece, instant, system)
            if got == want:
                continue
            bad += 1
            if args.quiet or bad > 5:
                continue
            missing = set(want) - set(got)
            extra = set(got) - set(want)
            spins = {c for c in set(got) & set(want) if got[c] != want[c]}
            print(f"MISMATCH {piece.name} rows={rows}")
            print(f"  missing={len(missing)} extra={len(extra)} "
                  f"spin-diff={len(spins)}")
            if missing:
                print("   e.g. missing", sorted(next(iter(missing))))
            if extra:
                print("   e.g. extra  ", sorted(next(iter(extra))))

    checked = len(stacks) * len(PieceType)
    print(f"{system.name}, {args.mode} descent: {checked} comparisons "
          f"({len(stacks)} stacks x {len(PieceType)} pieces), {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
