"""Exact cover of a line's region, including stretched footprints."""
from itertools import combinations, combinations_with_replacement

from tetris_sdk.opener.tiling import _shapes, _variants, tile
from tetris_sdk.pieces import PieceType

BAG = tuple(PieceType[ch] for ch in "TILJSZO")


def _rect(rows, cols):
    return frozenset((r, c) for r in range(rows) for c in range(cols))


def test_no_five_distinct_pieces_tile_the_two_row_strip():
    # OPENER_SEARCH_NOTES.md §3: a 2-line PC segment is impossible.
    for pool in combinations(BAG, 5):
        assert tile(_rect(2, 10), pool) == []


def test_two_by_four_needs_a_duplicate_type():
    counts = {}
    for pool in combinations_with_replacement(BAG, 2):
        found = tile(_rect(2, 4), pool)
        counts[pool] = len(found)
        for tiling in found:
            cells = [c for _, cs in tiling for c in cs]
            assert len(cells) == len(set(cells)) == 8
    doubles = {(p, p): 1 for p in
               (PieceType.I, PieceType.O, PieceType.L, PieceType.J)}
    assert {k: v for k, v in counts.items() if v} == doubles


def test_size_mismatch_is_rejected_without_search():
    assert tile(_rect(2, 4), (PieceType.O,)) == []


def test_variants_stretch_only_across_cleared_rows():
    # Vertical I anchored at row 0, one cleared row inside its span.
    vertical_i = next(s for s in _shapes(PieceType.I)
                      if len({r for r, _ in s}) == 4)
    plain = _variants(vertical_i, 0, 0, frozenset())
    assert plain == [frozenset({(0, 0), (1, 0), (2, 0), (3, 0)})]

    stretched = _variants(vertical_i, 0, 0, frozenset({2}))
    assert frozenset({(0, 0), (1, 0), (3, 0), (4, 0)}) in stretched
    assert frozenset({(0, 0), (1, 0), (2, 0), (3, 0)}) in stretched
    assert len(stretched) == 2

    # A cleared row outside the span changes nothing.
    assert _variants(vertical_i, 0, 0, frozenset({9})) == plain
