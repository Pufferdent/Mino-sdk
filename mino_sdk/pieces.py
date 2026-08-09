from __future__ import annotations

from enum import IntEnum

from mino_sdk.types import Cell


class PieceType(IntEnum):
    """The seven standard guideline tetromino types.

    Each member's integer value matches the corresponding ``Cell`` value.
    """

    T = 1
    I = 2
    L = 3
    J = 4
    S = 5
    Z = 6
    O = 7

    @property
    def cell(self) -> Cell:
        """The ``Cell`` enum value used to render this piece on a board."""
        return Cell(self.value)


# Offset tuple type: (row, col) relative to the piece origin.
Offset = tuple[int, int]


def _rotate_cw(cells: list[Offset], n: int) -> list[Offset]:
    """Rotate offsets 90 degrees clockwise within an ``n`` x ``n`` box.

    Coordinates use row-increasing-upward (board) convention. A clockwise turn
    in that frame maps ``(r, c) -> (n - 1 - c, r)``, keeping all offsets within
    ``[0, n-1]``. This makes rotation index ``1`` the guideline "R" state (a
    clockwise turn from spawn) and index ``3`` the "L" state, so the rotation
    shapes agree with the kick tables (which are keyed for clockwise index
    increments) for every piece — not just the symmetric I.
    """
    return [(n - 1 - c, r) for r, c in cells]


def _generate_states(spawn: list[Offset], n: int) -> list[list[Offset]]:
    """Produce 4 rotation states by repeatedly rotating ``spawn`` clockwise."""
    states = [spawn]
    current = spawn
    for _ in range(3):
        current = _rotate_cw(current, n)
        states.append(current)
    return states


# Spawn shapes (row, col offsets) in board convention (row 0 = bottom of box).
# 3x3 box for J, L, S, T, Z; 4x4 for I; 2x2 for O.
_SPAWN_SHAPES: dict[PieceType, tuple[list[Offset], int]] = {
    PieceType.T: ([(1, 0), (1, 1), (1, 2), (2, 1)], 3),
    PieceType.J: ([(1, 0), (1, 1), (1, 2), (2, 0)], 3),
    PieceType.L: ([(1, 0), (1, 1), (1, 2), (2, 2)], 3),
    PieceType.S: ([(1, 0), (1, 1), (2, 1), (2, 2)], 3),
    PieceType.Z: ([(1, 1), (1, 2), (2, 0), (2, 1)], 3),
    PieceType.I: ([(2, 0), (2, 1), (2, 2), (2, 3)], 4),
    PieceType.O: ([(0, 0), (0, 1), (1, 0), (1, 1)], 2),
}


# SRS wall kick tables, keyed by (from_rotation, to_rotation) -> test offsets.
# Rotation indices: 0 = spawn, 1 = right (R), 2 = 180, 3 = left (L).
#
# Offsets are (drow, dcol) deltas in the board's row-increasing-upward frame
# (the same convention as Piece.cells): a kick test is (row + drow, col + dcol).
# These are the guideline SRS values; canonical references list them as (x, y)
# with y pointing up, so each entry here is (y, x). The first test is always
# (0, 0). Correctness is pinned by the T-spin fumen tests.
_JLSTZ_KICKS: dict[tuple[int, int], list[Offset]] = {
    (0, 1): [(0, 0), (0, -1), (1, -1), (-2, 0), (-2, -1)],
    (1, 0): [(0, 0), (0, 1), (-1, 1), (2, 0), (2, 1)],
    (1, 2): [(0, 0), (0, 1), (-1, 1), (2, 0), (2, 1)],
    (2, 1): [(0, 0), (0, -1), (1, -1), (-2, 0), (-2, -1)],
    (2, 3): [(0, 0), (0, 1), (1, 1), (-2, 0), (-2, 1)],
    (3, 2): [(0, 0), (0, -1), (-1, -1), (2, 0), (2, -1)],
    (3, 0): [(0, 0), (0, -1), (-1, -1), (2, 0), (2, -1)],
    (0, 3): [(0, 0), (0, 1), (1, 1), (-2, 0), (-2, 1)],
}

_I_KICKS: dict[tuple[int, int], list[Offset]] = {
    (0, 1): [(0, 0), (0, -2), (0, 1), (-1, -2), (2, 1)],
    (1, 0): [(0, 0), (0, 2), (0, -1), (1, 2), (-2, -1)],
    (1, 2): [(0, 0), (0, -1), (0, 2), (2, -1), (-1, 2)],
    (2, 1): [(0, 0), (0, 1), (0, -2), (-2, 1), (1, -2)],
    (2, 3): [(0, 0), (0, 2), (0, -1), (1, 2), (-2, -1)],
    (3, 2): [(0, 0), (0, -2), (0, 1), (-1, -2), (2, 1)],
    (3, 0): [(0, 0), (0, 1), (0, -2), (-2, 1), (1, -2)],
    (0, 3): [(0, 0), (0, -1), (0, 2), (2, -1), (-1, 2)],
}

# --- SRS+ (true TETR.IO) kick data -----------------------------------------
# I-piece 90 kicks for SRS+: the SRS I kicks reflected along the column axis
# (negate dcol), giving the y-axis-symmetric I kicks SRS+ uses.
_I_KICKS_PLUS: dict[tuple[int, int], list[Offset]] = {
    transition: [(dr, -dc) for dr, dc in offsets]
    for transition, offsets in _I_KICKS.items()
}

# 180 kick tables (transitions 0<->2 and 1<->3). Sourced from the TETR.IO
# engine (recorded in research/rotation-kick-tables-180.md) as [x, y] with y
# pointing DOWN; converted here to (drow, dcol) = (-y, x) for the row-up frame,
# with (0, 0) prepended.
_JLSTZ_180: dict[tuple[int, int], list[Offset]] = {
    (0, 2): [(0, 0), (1, 0), (1, 1), (1, -1), (0, 1), (0, -1)],
    (2, 0): [(0, 0), (-1, 0), (-1, -1), (-1, 1), (0, -1), (0, 1)],
    (1, 3): [(0, 0), (0, 1), (2, 1), (1, 1), (2, 0), (1, 0)],
    (3, 1): [(0, 0), (0, -1), (2, -1), (1, -1), (2, 0), (1, 0)],
}

_I_180: dict[tuple[int, int], list[Offset]] = {
    (0, 2): [(0, 0), (1, 0)],
    (2, 0): [(0, 0), (-1, 0)],
    (1, 3): [(0, 0), (0, 1)],
    (3, 1): [(0, 0), (0, -1)],
}


class RotationSystem:
    """Abstract base for a pluggable rotation system.

    Subclasses provide rotation shapes and wall kick data per piece type,
    decoupling rotation rules from piece identity so that multiple systems
    (SRS, Arika, Classic, ...) can coexist.
    """

    name: str = ""

    # Systems are stateless: two instances of the same class are the same
    # system. Value equality lets caches keyed on a system share entries.
    def __eq__(self, other) -> bool:
        return type(self) is type(other)

    def __hash__(self) -> int:
        return hash(type(self))

    def rotations(self, piece_type: PieceType) -> list[list[Offset]]:
        """Return 4 rotation states, each a list of ``(row, col)`` offsets."""
        raise NotImplementedError

    def kicks(
        self, piece_type: PieceType, from_rot: int, to_rot: int
    ) -> list[Offset]:
        """Return ``(row_offset, col_offset)`` wall kick test positions."""
        raise NotImplementedError


class SRS(RotationSystem):
    """The guideline Super Rotation System.

    Rotation shapes and kick tables are verified against Techmino's
    ``RSlist.lua`` and ``gameTables.lua``.
    """

    name = "SRS"

    def __init__(self) -> None:
        self._rotations: dict[PieceType, list[list[Offset]]] = {
            piece_type: _generate_states(spawn, n)
            for piece_type, (spawn, n) in _SPAWN_SHAPES.items()
        }

    def rotations(self, piece_type: PieceType) -> list[list[Offset]]:
        return self._rotations[piece_type]

    def kicks(
        self, piece_type: PieceType, from_rot: int, to_rot: int
    ) -> list[Offset]:
        if piece_type == PieceType.O:
            return []
        if piece_type == PieceType.I:
            return list(_I_KICKS.get((from_rot, to_rot), []))
        return list(_JLSTZ_KICKS.get((from_rot, to_rot), []))


class SRSPlus(SRS):
    """TETR.IO's SRS+ rotation system.

    Shares SRS rotation shapes. The JLSTZ 90-degree kicks are identical to
    SRS; the I-piece 90-degree kicks are the y-axis-symmetric SRS+ variant;
    and 180-degree kicks are defined for all four 180 transitions (O excepted).
    180 kick data is recorded in ``research/rotation-kick-tables-180.md``.
    """

    name = "SRS+"

    def kicks(
        self, piece_type: PieceType, from_rot: int, to_rot: int
    ) -> list[Offset]:
        if piece_type == PieceType.O:
            return []
        transition = (from_rot, to_rot)
        is_180 = transition in _JLSTZ_180
        if piece_type == PieceType.I:
            table = _I_180 if is_180 else _I_KICKS_PLUS
        else:
            table = _JLSTZ_180 if is_180 else _JLSTZ_KICKS
        return list(table.get(transition, []))


class Piece:
    """An active tetromino positioned on a board.

    The origin ``(row, col)`` is the bottom-left corner of the piece's
    bounding box. ``row`` increases upward, matching the ``Board`` grid.
    """

    def __init__(
        self,
        type: PieceType,
        rotation: int = 0,
        row: int = 0,
        col: int = 0,
        system: RotationSystem | None = None,
    ) -> None:
        self.type = type
        self.rotation = rotation
        self.row = row
        self.col = col
        self.system = system if system is not None else SRS()

    @property
    def cells(self) -> list[Offset]:
        """Absolute ``(row, col)`` board positions occupied by the piece."""
        offsets = self.system.rotations(self.type)[self.rotation]
        return [(self.row + dr, self.col + dc) for dr, dc in offsets]

    def copy(self, **overrides) -> "Piece":
        """Return a new ``Piece`` with optional attribute overrides.

        The rotation ``system`` is preserved unless overridden.
        """
        return Piece(
            type=overrides.get("type", self.type),
            rotation=overrides.get("rotation", self.rotation),
            row=overrides.get("row", self.row),
            col=overrides.get("col", self.col),
            system=overrides.get("system", self.system),
        )


def get_piece_cells(
    piece_type: PieceType,
    rotation: int = 0,
    x: int = 0,
    y: int = 0,
    coord_system: str = "sdk",
) -> list[Offset]:
    if not (0 <= rotation <= 3):
        raise ValueError(f"Rotation must be 0-3, got {rotation}")
    if coord_system not in ("sdk", "fumen"):
        raise ValueError(f"coord_system must be 'sdk' or 'fumen', got {coord_system!r}")

    spawn, n = _SPAWN_SHAPES[piece_type]
    offsets = spawn
    for _ in range(rotation):
        offsets = _rotate_cw(offsets, n)

    cells: list[Offset] = [(y + dr, x + dc) for dr, dc in offsets]

    if coord_system == "fumen":
        cells = [(dc, dr) for dr, dc in cells]

    return cells
