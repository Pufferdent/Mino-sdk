## 1. Fumen Pipeline — Foundations

- [x] 1.1 Add piece type mapping tables (`FUMEN_PIECE_TO_TYPE`, `TYPE_TO_FUMEN_PIECE`) to `mino_sdk/fumen/decoder.py` and export from package
- [x] 1.2 Create `mino_sdk/coords.py` with coordinate conversion utilities (`fumen_row_to_board_row`, `board_row_to_fumen_row`, `fumen_position_to_row_col`)
- [x] 1.3 Export new symbols from `mino_sdk/__init__.py`

## 2. Fumen Pipeline — MultiFumenPage

- [x] 2.1 Create `mino_sdk/fumen/multi_fumen.py` with `Page` dataclass (board, comment) and `MultiFumenPage` class
- [x] 2.2 Implement `MultiFumenPage.from_string()` classmethod that parses v115 into list of Pages
- [x] 2.3 Add tests for single-page, multi-page, comments, color-mode pages
- [x] 2.4 Export `MultiFumenPage` and `Page` from package

## 3. Fumen Pipeline — Board String Utilities

- [x] 3.1 Add `board_to_string()` to `mino_sdk/board.py`: convert bottom 4 rows to 40-char string (top-to-bottom, N/X/piece glyphs)
- [x] 3.2 Add `board_from_string()` to `mino_sdk/board.py`: parse 40-char string to Board cells (row 0 = bottom)
- [x] 3.3 Add round-trip tests
- [x] 3.4 Export from package

## 4. Fumen Pipeline — Piece Shape Computation

- [x] 4.1 Add `get_piece_cells(type, rotation, x, y, coord_system='sdk')` to `mino_sdk/pieces.py`
- [x] 4.2 Support `coord_system='fumen'` mode returning (x, y) tuples with y=0 as bottom
- [x] 4.3 Add tests for all 7 piece types, all 4 rotations, both coordinate systems
- [x] 4.4 Export from package

## 5. Fumen Pipeline — Fumen Encoding

- [x] 5.1 Create `mino_sdk/fumen/encoder.py` with `encode_fumen(pages)` function
- [x] 5.2 Implement base64 encoding and field run-length encoding (inverse of `_read_field`)
- [x] 5.3 Implement piece operation encoding (inverse of `_read_piece`)
- [x] 5.4 Implement comment encoding (inverse of `_read_comment`)
- [x] 5.5 Add round-trip tests: encode then decode and verify board/comment match
- [x] 5.6 Export from package

## 6. Fumen Pipeline — Color-Mode Decoding

- [x] 6.1 Update `parse_fumen` and `MultiFumenPage.from_string()` to detect page `color` flag
- [x] 6.2 When `color=True`, preserve field values > 8 as `Cell.GARBAGE` (no clamping loss)
- [x] 6.3 Add tests with color-mode fumen fixtures

## 7. Solver — Queue Validation

- [x] 7.1 Create `mino_sdk/solver/queue_validator.py` with `is_placement_order_valid()` and `enumerate_placement_orders()`
- [x] 7.2 Implement standard hold rules (swap once per piece placement, can't hold twice without placing)
- [x] 7.3 Implement sfinder hold mode (unlimited swaps)
- [x] 7.4 Implement no-hold mode
- [x] 7.5 Add tests for valid/invalid orders, enumeration correctness

## 8. Solver — Core PC Solver

- [x] 8.1 Create `mino_sdk/solver/core.py` with `solve_pc()` function
- [x] 8.2 Implement DFS with board-state memoization keyed by (board_hash, queue_position, hold_state)
- [x] 8.3 Support `hold='standard'|'sfinder'|'none'`, `head_hold`, `max_solutions`, `clear_lines`
- [x] 8.4 Accept board as `Board` object or 40-char string (auto-detect)
- [x] 8.5 Return `Solution` objects with piece_order, board_states, operations, unused_pieces, topological_orderings
- [x] 8.6 Compute topological orderings using piece physics (no cell overlap, support below min-row per column)
- [x] 8.7 Add tests for known PC setups, edge cases, no-solution cases

## 9. Solver — Wanted-Saves Expression Parser

- [x] 9.1 Create `mino_sdk/solver/expressions.py` with tokenizer, recursive-descent parser, and AST node classes
- [x] 9.2 Support operators: `||` (OR), `&&` (AND), `!` (NOT), `^` (AVOID)
- [x] 9.3 Support literals: piece strings (`TILJSZO`), regex (`/pattern/`)
- [x] 9.4 Implement `evaluate_ast(node, saves)` and `evaluate_ast_all(node, saves)` evaluators
- [x] 9.5 Add tests for all operator combinations, nested expressions, regex matching, edge cases

## 10. Solver — Save Analysis

- [x] 10.1 Create `mino_sdk/solver/saves.py` with save percentage computation and solve filtering
- [x] 10.2 Implement `compute_save_percentage(solves, expression, over_solves=False)`
- [x] 10.3 Implement `filter_solves(solves, expression)` returning matching solves
- [x] 10.4 Add tests with known save distributions

## 11. Solver — Package Wiring

- [x] 11.1 Create `mino_sdk/solver/__init__.py` exporting all public symbols
- [x] 11.2 Import and re-export solver symbols from `mino_sdk/__init__.py`
- [x] 11.3 Add solver module to package setup/config if needed

## 12. Integration & Polish

- [x] 12.1 Review all exports in `mino_sdk/__init__.py` for consistency
- [x] 12.2 Run full test suite, fix any regressions
- [x] 12.3 Verify all imports resolve correctly
