## 1. Package Scaffold

- [x] 1.1 Create `mino_sdk/` package directory with `__init__.py`
- [x] 1.2 Create `mino_sdk/types.py` with `Cell` IntEnum (EMPTY=0, T=1, I=2, L=3, J=4, S=5, Z=6, O=7, GARBAGE=8, SOLID=9)

## 2. Board Core

- [x] 2.1 Implement `Board` class constructor with 40×10 grid (Row 0 = bottom, Row 39 = top)
- [x] 2.2 Implement `get_cell(row, col)` returning Cell enum value
- [x] 2.3 Implement `set_cell(row, col, value)` with bounds checking (raise IndexError on out-of-bounds)
- [x] 2.4 Implement `is_row_full(row)` returning True if all 10 cells are non-EMPTY
- [x] 2.5 Implement `clear_lines()` — detect all full rows, remove them, shift above rows down, pad top with empty rows
- [x] 2.6 Implement `__str__` and `__repr__` for ASCII debug output (top-to-bottom display)

## 3. Fumen Parser

- [x] 3.1 Create `mino_sdk/fumen/` package with `__init__.py`
- [x] 3.2 Implement `mino_sdk/fumen/decoder.py` with low-level helpers: version extraction, base64 decode, zlib decompress, RLE decoding of field data
- [x] 3.3 Implement `mino_sdk/fumen/parser.py` with `parse_fumen(fumen_str: str) -> list[Board]` public API
- [x] 3.4 Validate fumen version prefix (v115@) and raise ValueError for unsupported/missing versions
- [x] 3.5 Handle multi-page fumen strings, returning one Board per page

## 4. Tests

- [x] 4.1 Write tests for Board: dimensions, cell get/set for each of the 10 states, bounds checking, is_row_full (non-EMPTY), line clear (single, multiple, none, SOLID persistence), string representation with colored glyphs
- [x] 4.2 Write tests for fumen parsing: version validation, empty board round-trip, piece-colored cells, GARBAGE/ SOLID cell preservation, multi-page parsing
- [x] 4.3 Validate the provided sample fumen (`v115@AhBtDewhBeBtEewhCeR4De0hR4CewhJeAgH`) parses correctly — verify known cell positions in resulting Board
