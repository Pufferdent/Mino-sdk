## 1. Event model and classification (events.py)

- [x] 1.1 Create `tetris_sdk/events.py` with `EventKind(Enum)` — `PLACEMENT, SPIN, CLEAR` — and a frozen, hashable `Event` dataclass: `kind, piece, spin, lines, name, difficult, back_to_back, b2b, combo, perfect_clear`
- [x] 1.2 Add `B2BRule(Enum)` — `S1, S2`
- [x] 1.3 Implement `classify_lock(piece, spin, lines) -> tuple[EventKind, str]`: kind from `(lines, spin)`; name per the table (Placement; spin-0 names; Single/Double/Triple/`Quad`; T-Spin [Mini] Single/Double/Triple; `<P>-Spin <Lines>`)
- [x] 1.4 Implement `is_difficult(piece, spin, lines, rule) -> bool`: false if `lines == 0`; true if `lines == 4`; else S1 → `piece == T and spin != NONE`, S2 → `spin != NONE`

## 2. Board running state & lock (board.py)

- [x] 2.1 Add `b2b: int = 0`, `combo: int = 0`, `b2b_rule: B2BRule = B2BRule.S2` to `Board.__init__`; ensure `from_fumen` boards start at the defaults
- [x] 2.2 Implement `Board.lock(piece, spin=SpinType.NONE) -> Event` — place (raise `ValueError` if invalid), clear full rows, count `lines`, classify via `classify_lock`
- [x] 2.3 Apply back-to-back update using `is_difficult(..., self.b2b_rule)`: non-clearing lock preserves `b2b`; difficult clear sets `back_to_back = b2b > 0` then increments `b2b`; non-difficult clear resets `b2b = 0`
- [x] 2.4 Apply combo update: increment on CLEAR, reset to 0 on PLACEMENT/SPIN
- [x] 2.5 Compute `perfect_clear` (board empty after the clear) and assemble the `Event`
- [x] 2.6 Ensure a raised `ValueError` (invalid placement) leaves `b2b`/`combo` unchanged

## 3. Public API

- [x] 3.1 Export `Event`, `EventKind`, `B2BRule` from `tetris_sdk/__init__.py` and add to `__all__`

## 4. Tests

- [x] 4.1 `tests/test_events.py` — `EventKind` from `(lines, spin)`: PLACEMENT, SPIN (spin-0), CLEAR
- [x] 4.2 `tests/test_events.py` — `classify_lock` names: `Quad` for 4 lines; Single/Double/Triple; `T-Spin Double`; `T-Spin Mini Single`; `S-Spin Single`; spin-0 → `T-Spin Mini`/`<P>-Spin`; placement → `Placement`
- [x] 4.3 `tests/test_events.py` — `is_difficult`: 0 lines never; quad both rules; S1 excludes non-T spin, includes T-spin; S2 includes any spin; mini T-spin clears difficult both rules
- [x] 4.4 `tests/test_events.py` — `Event` hashability/equality and full field set
- [x] 4.5 `tests/test_board.py` — new board defaults `b2b == 0`, `combo == 0`, `b2b_rule == S2`; configurable rule; fumen board likewise
- [x] 4.6 `tests/test_board.py` — `lock` returns CLEAR with `lines`/`name` consistent with `(piece, spin)`; uses supplied spin verbatim (T,FULL,2 → `T-Spin Double`); spin-0 yields SPIN event
- [x] 4.7 `tests/test_board.py` — B2B chain: first difficult → `back_to_back False`, `b2b 1`; second → `back_to_back True`, `b2b 2`; non-difficult clear resets `b2b 0`; spin-0 preserves `b2b`
- [x] 4.8 `tests/test_board.py` — rule selection: S-spin single is non-difficult under S1, difficult under S2
- [x] 4.9 `tests/test_board.py` — combo increments across consecutive clears; resets on PLACEMENT/SPIN
- [x] 4.10 `tests/test_board.py` — perfect clear true when emptied, false with residue; invalid placement raises and leaves state unchanged
